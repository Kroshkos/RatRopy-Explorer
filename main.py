import flet as ft
import math
import datetime
from collections import defaultdict
import sqlite3
from fpdf import FPDF
import os
import json
import asyncio

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('ratropy.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS animals (
        id TEXT PRIMARY KEY,
        species TEXT,
        age TEXT,
        weight TEXT,
        info TEXT
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        animal_id TEXT,
        date TEXT,
        attempt TEXT,
        events TEXT,
        entropy REAL,
        FOREIGN KEY (animal_id) REFERENCES animals (id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

# Функции работы с БД
def add_animal_db(animal):
    conn = sqlite3.connect('ratropy.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO animals (id, species, age, weight, info)
        VALUES (?, ?, ?, ?, ?)
    ''', (animal['id'], animal['species'], animal['age'], animal['weight'], animal['info']))
    conn.commit()
    conn.close()

def update_animal_db(animal):
    conn = sqlite3.connect('ratropy.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE animals
        SET species = ?, age = ?, weight = ?, info = ?
        WHERE id = ?
    ''', (animal['species'], animal['age'], animal['weight'], animal['info'], animal['id']))
    conn.commit()
    conn.close()

def get_animals_db():
    conn = sqlite3.connect('ratropy.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM animals')
    animals = [dict(zip(['id', 'species', 'age', 'weight', 'info'], row)) for row in cursor.fetchall()]
    conn.close()
    return animals

def get_animal_db(animal_id):
    conn = sqlite3.connect('ratropy.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM animals WHERE id = ?', (animal_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(zip(['id', 'species', 'age', 'weight', 'info'], row))
    return None

def add_experiment_db(experiment):
    conn = sqlite3.connect('ratropy.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO experiments (animal_id, date, attempt, events, entropy)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        experiment['animal_id'],
        experiment['date'],
        experiment['attempt'],
        json.dumps(experiment['events']),
        experiment['entropy']
    ))
    conn.commit()
    conn.close()

def get_experiments_db():
    conn = sqlite3.connect('ratropy.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT experiments.*, animals.species 
        FROM experiments
        LEFT JOIN animals ON experiments.animal_id = animals.id
    ''')
    experiments = []
    for row in cursor.fetchall():
        exp = dict(zip(
            ['id', 'animal_id', 'date', 'attempt', 'events', 'entropy', 'species'],
            row
        ))
        exp['events'] = json.loads(exp['events'])
        experiments.append(exp)
    conn.close()
    return experiments

def get_experiment_db(experiment_id):
    conn = sqlite3.connect('ratropy.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT experiments.*, animals.species 
        FROM experiments
        LEFT JOIN animals ON experiments.animal_id = animals.id
        WHERE experiments.id = ?
    ''', (experiment_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        exp = dict(zip(
            ['id', 'animal_id', 'date', 'attempt', 'events', 'entropy', 'species'],
            row
        ))
        exp['events'] = json.loads(exp['events'])
        return exp
    return None

# Основное приложение
def main(page: ft.Page):
    page.title = "RatRopy Explorer"
    page.theme_mode = ft.ThemeMode.DARK  # Исправлено на темную тему
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # Глобальные переменные состояния
    current_experiment = None
    timer_running = False
    start_time = None
    timer_text = ft.Text("00:00:00", size=24)
    events_list = ft.Ref[ft.ListView]()
    selected_animal_id = None
    BEHAVIORS = [
        "Горизонтальное положение",
        "Центральная стойка",
        "Переферическая стойка",
        "Груминг",
        "Замирание",
        "Заглядывание в норки",
        "Обнюхивание"
    ]

    # Расчет энтропии
    def calculate_entropy(events):
        acts = [e[1] for e in events]
        n = len(acts)
        if n == 0:
            return 0

        # Вероятности отдельных актов
        p_i = defaultdict(int)
        for act in acts:
            p_i[act] += 1
        for k in p_i:
            p_i[k] /= n

        # Вероятности пар
        p_ij = defaultdict(lambda: defaultdict(int))
        counts_j = defaultdict(int)
        for i in range(1, n):
            prev = acts[i-1]
            curr = acts[i]
            p_ij[prev][curr] += 1
            counts_j[prev] += 1
        
        # Вероятности троек
        p_ijk = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        counts_ij = defaultdict(lambda: defaultdict(int))
        for i in range(2, n):
            prev2 = acts[i-2]
            prev1 = acts[i-1]
            curr = acts[i]
            p_ijk[prev2][prev1][curr] += 1
            counts_ij[prev2][prev1] += 1

        # Вычисление энтропии
        H1 = 0
        for pi in p_i.values():
            if pi > 0:
                H1 -= pi * math.log2(pi)

        H2 = 0
        for j, transitions in p_ij.items():
            for count in transitions.values():
                p = count / counts_j[j]
                if p > 0:
                    H2 -= p * math.log2(p)

        H3 = 0
        for i, row in p_ijk.items():
            for j, transitions in row.items():
                for count in transitions.values():
                    p = count / counts_ij[i][j]
                    if p > 0:
                        H3 -= p * math.log2(p)

        return H1 + H2 + H3

    # Генерация PDF отчета
    def generate_pdf(experiment, animal):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Заголовок
        pdf.cell(0, 10, f"Отчет об исследовании - {experiment['date']}", 0, 1, 'C')
        pdf.ln(10)
        
        # Паспортные данные
        pdf.cell(0, 10, "Паспортная часть:", 0, 1)
        pdf.cell(0, 10, f"Животное: {animal['id']} ({animal['species']})", 0, 1)
        pdf.cell(0, 10, f"Возраст: {animal['age']}, Вес: {animal['weight']}", 0, 1)
        pdf.ln(5)
        
        # Результаты
        pdf.cell(0, 10, f"Показатель энтропии: {experiment['entropy']:.4f}", 0, 1)
        pdf.ln(10)
        
        # История событий
        pdf.cell(0, 10, "История поведенческих актов:", 0, 1)
        for time, event in experiment['events']:
            pdf.cell(0, 10, f"{time} - {event}", 0, 1)
        
        # Сохранение файла
        filename = f"report_{animal['id']}_{experiment['date'].replace(' ', '_')}.pdf"
        pdf.output(filename)
        return filename

    # Диалог сохранения файла
    def save_file_result(e: ft.FilePickerResultEvent):
        if e.path:
            animal = get_animal_db(current_experiment['animal_id'])
            filename = generate_pdf(current_experiment, animal)
            os.rename(filename, e.path)
            page.snack_bar = ft.SnackBar(ft.Text(f"Отчет сохранен: {e.path}"))
            page.snack_bar.open = True
        page.update()

    file_picker = ft.FilePicker(on_result=save_file_result)
    page.overlay.append(file_picker)

    # Форматирование времени
    def format_time(seconds):
        return str(datetime.timedelta(seconds=seconds))

    # Обновление таймера
    # Замените функцию update_timer на следующую версию:
    async def update_timer():
        nonlocal timer_running
        while timer_running:
            elapsed = datetime.datetime.now() - start_time
            seconds = int(elapsed.total_seconds())
            timer_text.value = format_time(seconds)
            # Обновляем всю страницу, а не только текстовый элемент
            await page.update_async()
            await asyncio.sleep(0.1)



    # Обработчики поведения
    def behavior_clicked(behavior):
        if timer_running:
            elapsed = datetime.datetime.now() - start_time
            seconds = int(elapsed.total_seconds())
            time_str = format_time(seconds)
            current_experiment['events'].append((time_str, behavior))
            
            events_list.current.controls.append(
                ft.ListTile(
                    title=ft.Text(behavior),
                    subtitle=ft.Text(time_str)
                )
            )
            events_list.current.update()

    # Завершение исследования
    def finish_experiment(e):
        nonlocal timer_running
        timer_running = False
        current_experiment['entropy'] = calculate_entropy(current_experiment['events'])
        add_experiment_db(current_experiment)
        show_report(current_experiment)



    # Начало исследования
    def start_experiment(e):
        nonlocal current_experiment, timer_running, start_time
        date = date_input.value
        animal_id = animal_id_input.value
        attempt = attempt_input.value

        if not all([date, animal_id, attempt]):
            page.snack_bar = ft.SnackBar(ft.Text("Заполните все поля!"))
            page.snack_bar.open = True
            page.update()
            return

        animal = get_animal_db(animal_id)
        if not animal:
            page.snack_bar = ft.SnackBar(ft.Text(f"Животное с ID {animal_id} не найдено!"))
            page.snack_bar.open = True
            page.update()
            return

        current_experiment = {
            'animal_id': animal_id,
            'date': date,
            'attempt': attempt,
            'events': [],
            'entropy': None
        }
        start_time = datetime.datetime.now()
        timer_running = True

        # Clear previous events
        if events_list.current:
            events_list.current.controls.clear()

        page.go("/experiment")
        page.update()

        # Запускаем таймер через page.run_task (передаем функцию, а не её вызов)
        page.run_task(update_timer)



    # Показать отчет
    def show_report(experiment):
        animal = get_animal_db(experiment['animal_id'])
        report_content.controls = [
            ft.Divider(),
            ft.Text(f"Дата: {experiment['date']}"),
            ft.Text(f"Животное: {animal['id']} ({animal['species']})"),
            ft.Text(f"Попытка: {experiment['attempt']}"),
            ft.Text(f"Энтропия: {experiment['entropy']:.4f}", size=20, color="blue"),
            ft.Text("История событий:", weight="bold")
        ]
        
        for time, event in experiment['events']:
            report_content.controls.append(ft.Text(f"{time} - {event}"))
        
        report_content.controls.append(
            ft.ElevatedButton(
                "Экспорт в PDF",
                icon=ft.Icons.PICTURE_AS_PDF,
                on_click=lambda _: file_picker.save_file()
            )
        )
        
        page.go("/report")
        page.update()

    # Добавление животного
    def add_animal(e):
        animal = {
            'id': id_input.value,
            'species': species_input.value,
            'age': age_input.value,
            'weight': weight_input.value,
            'info': info_input.value
        }
        add_animal_db(animal)
        page.snack_bar = ft.SnackBar(ft.Text(f"Животное {animal['id']} добавлено!"))
        page.snack_bar.open = True
        page.go("/")
        page.update()

    # Редактирование животного
    def save_animal_changes(e):
        animal = {
            'id': selected_animal_id,
            'species': edit_species_input.value,
            'age': edit_age_input.value,
            'weight': edit_weight_input.value,
            'info': edit_info_input.value
        }
        update_animal_db(animal)
        page.snack_bar = ft.SnackBar(ft.Text("Данные сохранены!"))
        page.snack_bar.open = True
        page.go("/animals")
        page.update()

    # UI Компоненты

    # Главный экран
    welcome_view = ft.Column(
        controls=[
            ft.Text("RatRopy Explorer", size=30, weight="bold"),
            ft.ElevatedButton("Новое исследование", on_click=lambda _: page.go("/new_experiment")),
            ft.ElevatedButton("Добавить животное", on_click=lambda _: page.go("/add_animal")),
            ft.ElevatedButton("Профиль животного", on_click=lambda _: page.go("/animals")),
            ft.ElevatedButton("История исследований", on_click=lambda _: page.go("/history"))
        ],
        spacing=20,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER
    )

    # Форма добавления животного
    id_input = ft.TextField(label="Учетный номер")
    species_input = ft.TextField(label="Вид животного")
    age_input = ft.TextField(label="Возраст")
    weight_input = ft.TextField(label="Вес")
    info_input = ft.TextField(label="Дополнительная информация", multiline=True)
    
    add_animal_view = ft.Column(
        controls=[
            ft.Text("Добавить животное", size=24),
            id_input,
            species_input,
            age_input,
            weight_input,
            info_input,
            ft.Row([
                ft.ElevatedButton("Назад", on_click=lambda _: page.go("/")),
                ft.ElevatedButton("Сохранить", on_click=add_animal)
            ], spacing=10)
        ],
        spacing=15
    )

    # Список животных
    animal_cards = ft.GridView(
        expand=True,
        runs_count=3,
        max_extent=300,
        child_aspect_ratio=3.0,
        spacing=10,
        run_spacing=10
    )
    
    def update_animal_cards():
        animal_cards.controls.clear()
        for animal in get_animals_db():
            animal_cards.controls.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.ListTile(
                                title=ft.Text(f"ID: {animal['id']}"),
                                subtitle=ft.Text(animal['species']),
                                on_click=lambda e, a=animal['id']: show_animal_detail(a)
                            )
                        ])
                    )
                )
            )
    
    animals_view = ft.Column(
        controls=[
            ft.Text("Профиль животного", size=24),
            animal_cards,
            ft.ElevatedButton("На главную", on_click=lambda _: page.go("/"))  # Добавлена кнопка
        ]
    )

    # Детали животного
    edit_species_input = ft.TextField(label="Вид животного")
    edit_age_input = ft.TextField(label="Возраст")
    edit_weight_input = ft.TextField(label="Вес")
    edit_info_input = ft.TextField(label="Дополнительная информация", multiline=True)
    
    animal_detail_view = ft.Column()
    
    def show_animal_detail(animal_id):
        nonlocal selected_animal_id
        selected_animal_id = animal_id
        animal = get_animal_db(animal_id)
        if animal:
            edit_species_input.value = animal['species']
            edit_age_input.value = animal['age']
            edit_weight_input.value = animal['weight']
            edit_info_input.value = animal['info']
            
            animal_detail_view.controls = [
                ft.Row([
                    ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _: page.go("/animals")),
                    ft.Text(f"Животное: {animal['id']}", size=20),
                ]),
                ft.Text(f"Вид: {animal['species']}"),
                ft.Text(f"Возраст: {animal['age']}"),
                ft.Text(f"Вес: {animal['weight']}"),
                ft.Text(f"Доп. информация: {animal['info']}"),
                ft.ElevatedButton("Редактировать", on_click=lambda _: toggle_edit_mode(True))
            ]
            page.go("/animal_detail")
            page.update()
    
    def toggle_edit_mode(edit):
        if edit:
            animal_detail_view.controls = [
                ft.Row([
                    ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _: page.go("/animals")),
                    ft.Text("Редактирование животного", size=20),
                ]),
                edit_species_input,
                edit_age_input,
                edit_weight_input,
                edit_info_input,
                ft.ElevatedButton("Сохранить", on_click=save_animal_changes)
            ]
        else:
            show_animal_detail(selected_animal_id)
        page.update()

    # Форма нового исследования
    date_input = ft.TextField(
        label="Дата",
        value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    animal_id_input = ft.TextField(label="Номер животного")
    attempt_input = ft.TextField(label="Номер попытки")
    
    new_experiment_view = ft.Column(
        controls=[
            ft.Row([
                ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _: page.go("/")),
                ft.Text("Новое исследование", size=24),
            ]),
            date_input,
            animal_id_input,
            attempt_input,
            ft.ElevatedButton("Начать исследование", on_click=start_experiment)
        ],
        spacing=15
    )

    # Экран исследования
    behavior_buttons = []
    for behavior in BEHAVIORS:
        # Используем замыкание для правильной привязки поведения
        def make_behavior_handler(b):
            return lambda e: behavior_clicked(b)
        
        behavior_buttons.append(
            ft.ElevatedButton(
                behavior, 
                on_click=make_behavior_handler(behavior),
                width=200,
                height=60
            )
        )
    
    experiment_view = ft.Column(
        controls=[
            ft.Row([
                ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda _: page.go("/")),
                ft.Text("Исследование", size=24),
            ]),
            ft.Row([
                ft.Column([
                    ft.Text("Паспортная часть", weight="bold"),
                    ft.Text(f"Животное: {current_experiment['animal_id'] if current_experiment else ''}"),
                    ft.Text(f"Попытка: {current_experiment['attempt'] if current_experiment else ''}")
                ]) if current_experiment else ft.Text(""),
                ft.ElevatedButton("Завершить", color="red", on_click=finish_experiment)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            #ft.Container(
                #content=timer_text,
                #alignment=ft.alignment.center,
                #padding=20
            #),
            ft.Text("Поведенческие акты:", weight="bold"),
            ft.Row(
                controls=behavior_buttons,
                wrap=True,
                spacing=10,
                run_spacing=10,
                scroll=ft.ScrollMode.AUTO
            ),
            ft.Text("История событий:", weight="bold"),
            ft.Container(
                content=ft.ListView(ref=events_list, expand=True),
                border=ft.border.all(1, ft.Colors.GREY_700),
                border_radius=10,
                padding=10,
                expand=True
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True
    )

    # Отчет об исследовании
    report_content = ft.Column()
    report_view = ft.Column(
        controls=[
            ft.Text("Отчет об исследовании", size=24),
            report_content,
            ft.ElevatedButton("На главную", on_click=lambda _: page.go("/"))
        ]
    )

    # История исследований
    history_cards = ft.ListView(expand=True)
    
    def update_history_cards():
        history_cards.controls.clear()
        for exp in get_experiments_db():
            history_cards.controls.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            title=ft.Text(f"Дата: {exp['date']}"),
                            subtitle=ft.Text(f"Животное: {exp['animal_id']} ({exp.get('species', 'N/A')})"),
                            trailing=ft.Text(f"Энтропия: {exp['entropy']:.4f}"),
                            on_click=lambda e, ex=exp['id']: show_experiment_report(ex)
                        ),
                        padding=10
                    )
                )
            )
    
    def show_experiment_report(exp_id):
        experiment = get_experiment_db(exp_id)
        if experiment:
            show_report(experiment)
    
    history_view = ft.Column(
        controls=[
            ft.Text("История исследований", size=24),
            history_cards,
            ft.ElevatedButton("На главную", on_click=lambda _: page.go("/"))
        ]
    )

    # Маршрутизация
    def route_change(route):
        page.views.clear()
        page.views.append(ft.View("/", [welcome_view]))
        
        if page.route == "/add_animal":
            page.views.append(ft.View("/add_animal", [add_animal_view]))
        
        elif page.route == "/animals":
            update_animal_cards()
            page.views.append(ft.View("/animals", [animals_view]))
        
        elif page.route == "/animal_detail":
            page.views.append(ft.View("/animal_detail", [animal_detail_view]))
        
        elif page.route == "/new_experiment":
            page.views.append(ft.View("/new_experiment", [new_experiment_view]))
        
        elif page.route == "/experiment":
            page.views.append(ft.View("/experiment", [experiment_view]))
        
        elif page.route == "/report":
            page.views.append(ft.View("/report", [report_view]))
        
        elif page.route == "/history":
            update_history_cards()
            page.views.append(ft.View("/history", [history_view]))
        
        page.update()

    page.on_route_change = route_change
    page.go(page.route)

if __name__ == "__main__":
    ft.app(target=main)