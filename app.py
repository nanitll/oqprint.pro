import os
import json
import requests
import pytz
from datetime import datetime
from waitress import serve
from bs4 import BeautifulSoup
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import mm
from flask import Flask, render_template, request, send_from_directory, jsonify
import re
from db import create_table, save_history, load_history  # Импортируем функции из db.py

app = Flask(__name__)

data_dir = os.path.join(app.root_path, 'data')
os.makedirs(data_dir, exist_ok=True)
stickers_dir = 'tmp/stickers'
os.makedirs(stickers_dir, exist_ok=True)
html_dir = 'tmp/_html'
os.makedirs(html_dir, exist_ok=True)

number_file = os.path.join(data_dir, 'number.json')

create_table()

def load_copycenters(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        copycenters = json.load(f)
    return copycenters

def sanitize_filename(filename):
    # Удаляет символы, которые могут быть проблемными в названиях файлов
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def fetch_order_details_via_url(order_number, copycenters): # Парсинг
    url = f"https://is-oq-print.3328432.ru/get_deal_attachments/{order_number}"

    # Скачиваем HTML-страницу
    response = requests.get(url)
    if response.status_code != 200:
        print("Ошибка при загрузке страницы:", response.status_code)
        return None
    os.makedirs(html_dir, exist_ok=True)
    
    # Сохраняем HTML в локальный файл
    html_filename = os.path.join(html_dir, f"{order_number}.html")
    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(response.text)

    # Парсим HTML с помощью BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    try:
        # Находим нужный тег с данными в формате JSON
        deal_data_script = soup.find("script", {"id": "deal_data"})
        if deal_data_script:
            deal_data_json = deal_data_script.string
            order_details = json.loads(deal_data_json)

            # Извлекаем необходимые данные
            return {
                "order_number": order_details["order_title"],
                "deal_num": order_details["deal_num"],
                "cost": order_details["order_cost"],
                "payment_type": order_details["payment_type"],
                "client_name": order_details["client_name"],
                "phone_number": order_details["phone"],
                "issue_date_time": order_details["issue_date"],
                "copycenter_name": order_details["issue_center"],
                "delivery_adress": order_details["delivery_address"],
                "barcode_quantity": order_details["number_of_items"]
            }
        else:
            print("Не удалось найти данные о сделке.")
            return None

    except Exception as e:
        print("Ошибка при извлечении информации о заказе:", e)
        return None

def create_sticker_pdf(order_details, copycenters): # Создание стикеров
    os.makedirs(stickers_dir, exist_ok=True)
    pdf_filename = os.path.join(stickers_dir, f"{sanitize_filename(order_details['order_number'])}.pdf")

    if os.path.exists(pdf_filename):
        base, ext = os.path.splitext(pdf_filename)
        counter = 1
        while os.path.exists(pdf_filename):
            pdf_filename = f"{base}_{counter}{ext}"
            counter += 1

    # Определяем размер страницы
    c = canvas.Canvas(pdf_filename, pagesize=(6 * 28.35, 6 * 28.35))

    # Полные пути к шрифтам и регистрация шрифтов
    font_path_regular = os.path.join(app.root_path, 'static', 'fonts', 'DejaVuSans.ttf')
    font_path_bold = os.path.join(app.root_path, 'static', 'fonts', 'DejaVuSans-Bold.ttf')
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path_regular))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path_bold))

    logo_path = os.path.join(app.root_path, 'static', 'pictures', 'logo.png')
    logo_delivery_path = os.path.join(app.root_path, 'static', 'pictures', 'logo_delivery.jpg')
    logo_prz_path = os.path.join(app.root_path, 'static', 'pictures', 'logo_prz.png')
    copycenter_number = None

    #Дату форматируем
    issue_date_entr = datetime.strptime(order_details["issue_date_time"], '%d.%m.%Y %H:%M:%S')
    order_details["issue_date_time"] = issue_date_entr.strftime('%d.%m.%Y')
    
    # Ищем номер копицентра
    for num, names in copycenters.items():
        if order_details['copycenter_name'] in names:
            copycenter_number = num
            break

    for i in range(order_details['barcode_quantity']):
        # Отрисовка изображения логотипа
        if os.path.exists(logo_path):
            c.drawImage(logo_path, 0, 130, width=1.35 * inch, height=0.5 * inch)

        # Создание текстового буфера
        text = c.beginText(10, 120)
        text.setFont("DejaVuSans-Bold", 7)
        text.textLine(f"Номер заказа: {order_details['order_number']} ({i + 1} из {order_details['barcode_quantity']})")

        # Установка стандартного шрифта
        text.setFont("DejaVuSans", 7)

        # Добавление строк с данными
        text.textLine("Стоимость:")
        text.textLine("Тип оплаты:")
        text.textLine("Телефон:")
        text.textLine("Имя клиента:")
        text.textLine("Дата выдачи:")
        if order_details['delivery_adress']:
            text.textLine("Адрес:")
        else:
            text.textLine("Копицентр:")

        # Добавление значений заказа
        text.setTextOrigin(63, 112)  # Перемещение курсора для значений
        text.setFont("DejaVuSans-Bold", 7)
        text.textLine(order_details['cost'])
        text.textLine(order_details['payment_type'])
        text.textLine(order_details['phone_number'])
        text.textLine(order_details['client_name'])
        text.textLine(order_details['issue_date_time'])

        # Обработка названия копицентра
        if order_details['delivery_adress']:
            copycenter_name = order_details['delivery_adress']
        else:
            copycenter_name = order_details['copycenter_name']
        wrapped_text = copycenter_name.split()
        current_line = ""

        for word in wrapped_text:
            if c.stringWidth(current_line + word, "DejaVuSans-Bold", 6) < 32 * mm:  # 40 мм ширина текста
                current_line += word + " "
            else:
                text.textLine(current_line.strip())
                current_line = word + " "

        if current_line:
            text.textLine(current_line.strip())

        # Отрисовка текста на странице
        c.drawText(text)

        # Номер копицентра или логотип доставки
        if order_details['delivery_adress']:
            if os.path.exists(logo_delivery_path):
                c.drawImage(logo_delivery_path, 10, 15, width=0.6 * inch, height=0.5 * inch)
        else:
            if copycenter_number == '0':
                if os.path.exists(logo_prz_path):
                    c.drawImage(logo_prz_path, 10, 15, width=0.6 * inch, height=0.5 * inch)
            else:
                c.setFont("DejaVuSans-Bold", 60) #54
                if int(copycenter_number) < 10:
                    c.drawString(10, 10, '0' + copycenter_number)
                else:
                    c.drawString(10, 10, copycenter_number)           

        # Контактная информация
        c.setFont("DejaVuSans-Bold", 7)
        c.drawString(90, 10, "+7(812)244-90-90")

        # Закрываем текущую страницу
        c.showPage()

    # Сохраняем PDF
    c.save()
    return pdf_filename

@app.route('/get_history/<order_number>', methods=['GET'])
def get_history(order_number):
    history = load_history(order_number)
    return jsonify(history)

@app.route('/generate_stickers', methods=['POST'])
def generate_stickers():
    order_number = request.form['order_number']
    copycenters = load_copycenters(number_file)
    order_details = fetch_order_details_via_url(order_number, copycenters)
    
    if order_details:
        pdf_filename = create_sticker_pdf(order_details, copycenters)
        
        # Сохраняем историю пробития стикеров с учетом московского времени
        moscow_tz = pytz.timezone('Europe/Moscow')
        timestamp = datetime.now(moscow_tz).strftime('%d.%m.%Y %H:%M:%S')
        save_history(order_number, timestamp)
        
        return os.path.basename(pdf_filename)
    else:
        return "Ошибка при генерации стикеров.", 500

@app.route('/play_sound', methods=['POST'])
def play_sound():
    order_number = request.form['order_number']
    copycenters = load_copycenters(number_file)
    order_details = fetch_order_details_via_url(order_number, copycenters)

    if order_details:
        copycenter_name = order_details['copycenter_name']
        copycenter_number = None
        for num, names in copycenters.items():
            if copycenter_name in names:
                copycenter_number = num
                break
        
        if order_details['delivery_adress']:
            message = f"Доставка до клиента"
        else:
            message = f"Копицентр {copycenter_name}, ячейка номер {copycenter_number}"

        # Возврат сообщения, чтобы клиент мог самостоятельно произнести его
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error"}), 500

@app.route('/stickers/<filename>')
def serve_stickers(filename):
    return send_from_directory(stickers_dir, filename)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    serve(app, host='127.0.0.1', port=3000)