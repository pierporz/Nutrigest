import sqlite3
import os
import time
import shutil
import sys
import configparser
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from datetime import date
from werkzeug.utils import secure_filename
from tkinter import Tk, filedialog, messagebox, simpledialog
import requests
import json
import threading
import webbrowser


app = Flask(__name__)

if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
LICENSE_FILE = os.path.join(BASE_PATH, 'license')
API_URL = 'https://script.google.com/macros/s/AKfycbySf389gYwY0Enq8mXOyqr9iZiIz5kMyup9acIpB8JNRU8MwVgvXtAM4wl9CAUxprNdxQ/exec'
API_KEY = 'asdnsiadnoienoiniopwefiefnw'

def get_machine_guid():
    if sys.platform.startswith('win'):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Cryptography") as key:
                return winreg.QueryValueEx(key, "MachineGuid")[0]
        except Exception:
            return None
    for path in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
    return None

def _deobfuscate(s: str) -> str:
    return ''.join(chr(ord(c) - 1) for c in s)

def verify_license():
    guid = get_machine_guid()
    if not guid:
        return False
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, 'r', encoding='utf-8') as f:
                stored = f.read().strip()
            return _deobfuscate(stored) == guid
        except Exception:
            return False
    root = Tk()
    root.withdraw()
    key = simpledialog.askstring('Licenza', 'Inserisci la chiave di licenza:')
    root.destroy()
    if not key:
        return False
    payload = {
        'api_key': API_KEY,
        'license_key': key,
        'machine_guid': guid,
    }
    try:
        resp = requests.post(API_URL, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            obf = data.get('obfuscated_guid')
            if obf:
                with open(LICENSE_FILE, 'w', encoding='utf-8') as f:
                    f.write(obf)
                return _deobfuscate(obf) == guid
    except Exception as e:
        root = Tk(); root.withdraw(); messagebox.showerror('Errore', str(e)); root.destroy()
    return False

# Load configuration with GUI helper
def ensure_config():
    cfg = configparser.ConfigParser()
    if os.path.exists('config.ini'):
        cfg.read('config.ini')
    data_dir = cfg.get('Paths', 'data_dir', fallback=None)
    if not data_dir:
        root = Tk()
        root.withdraw()
        messagebox.showinfo(
            "Configurazione",
            "Seleziona la cartella in cui salvare il database e gli allegati",
        )
        folder = filedialog.askdirectory(title="Cartella dati")
        root.destroy()
        if not folder:
            raise SystemExit("Nessuna cartella selezionata. Uscita.")
        os.makedirs(folder, exist_ok=True)
        # Copy default database when first configuring the data directory
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        default_db = os.path.join(base_path, 'nutriflap.db')
        dest_db = os.path.join(folder, 'nutriflap.db')
        if os.path.exists(default_db) and not os.path.exists(dest_db):
            shutil.copy2(default_db, dest_db)
        if not cfg.has_section('Paths'):
            cfg.add_section('Paths')
        cfg.set('Paths', 'data_dir', folder)
        with open('config.ini', 'w') as f:
            cfg.write(f)
        data_dir = folder
    return cfg, data_dir


config, DATA_DIR = ensure_config()

# Paths for database and attachments
DB = os.path.join(DATA_DIR, 'nutriflap.db')
ATTACH_FOLDER = os.path.join(DATA_DIR, 'attachments')

# Ensure directories exist
os.makedirs(ATTACH_FOLDER, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS  # cartella temporanea estratta dal .exe
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    sql_path = os.path.join(base_path, 'init_db.sql')
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read()
    conn = get_db()
    conn.executescript(sql)
    conn.commit()
    conn.close()



def parse_notes(notes):
    items = []
    if not notes:
        return items
    for part in notes.split('<br>'):
        if not part:
            continue
        title = ''
        desc = part
        if part.startswith('<b>') and '</b>' in part:
            end = part.index('</b>')
            title = part[3:end]
            desc = part[end + 4:].strip()
        items.append({'title': title, 'desc': desc})
    return items


@app.route('/change_data_dir')
def change_data_dir():
    global DATA_DIR, DB, ATTACH_FOLDER, config
    old_dir = DATA_DIR
    root = Tk()
    root.withdraw()
    new_dir = filedialog.askdirectory(title="Cartella dati", initialdir=old_dir)
    root.destroy()
    if not new_dir or new_dir == old_dir:
        return redirect(url_for('index'))
    try:
        os.makedirs(new_dir, exist_ok=True)
        shutil.copy2(DB, os.path.join(new_dir, 'nutriflap.db'))
        shutil.copytree(ATTACH_FOLDER, os.path.join(new_dir, 'attachments'), dirs_exist_ok=True)
        if not config.has_section('Paths'):
            config.add_section('Paths')
        config.set('Paths', 'data_dir', new_dir)
        with open('config.ini', 'w') as f:
            config.write(f)
        DATA_DIR = new_dir
        DB = os.path.join(DATA_DIR, 'nutriflap.db')
        ATTACH_FOLDER = os.path.join(DATA_DIR, 'attachments')
        os.makedirs(ATTACH_FOLDER, exist_ok=True)
        root = Tk(); root.withdraw(); messagebox.showinfo("Completato", "Cartella aggiornata"); root.destroy()
    except Exception as e:
        config.set('Paths', 'data_dir', old_dir)
        with open('config.ini', 'w') as f:
            config.write(f)
        root = Tk(); root.withdraw(); messagebox.showerror("Errore", str(e)); root.destroy()
    return redirect(url_for('index'))




@app.route('/')
def index():
    con = get_db()
    patients = con.execute('SELECT * FROM patients ORDER BY name COLLATE NOCASE').fetchall()
    con.close()
    return render_template('index.html', patients=patients)


@app.route('/new_patient', methods=['GET', 'POST'])
def new_patient():
    con = get_db()
    if request.method == 'POST':
        name = request.form['name']
        fiscal = request.form.get('fiscal_code')
        birth = request.form.get('birthdate')
        email = request.form.get('email')
        phone = request.form.get('phone')
        weight = request.form.get('weight')
        waist = request.form.get('waist')
        hip = request.form.get('hip')
        height = request.form.get('height')
        navel = request.form.get('navel')
        custom = request.form.get('custom')
        questions = con.execute('SELECT * FROM questions').fetchall()
        notes_parts = []
        for q in questions:
            ans = request.form.get(f"q{q['id']}")
            if ans:
                notes_parts.append(f"<b>{q['text']}</b> {ans}")
        notes = '<br>'.join(notes_parts)
        cur = con.cursor()
        cur.execute('INSERT INTO patients (name, birthdate, email, phone, fiscal_code, anamnesis) VALUES (?,?,?,?,?,?)',
                    (name, birth, email, phone, fiscal, notes))
        pid = cur.lastrowid
        cur.execute('INSERT INTO visits (patient_id, date, notes, weight, waist, hip, height, navel, custom) VALUES (?,?,?,?,?,?,?,?,?)',
                    (pid, date.today(), notes, weight, waist, hip, height, navel, custom))
        con.commit()
        con.close()
        return redirect(url_for('index'))
    questions = con.execute('SELECT * FROM questions').fetchall()
    con.close()
    return render_template('new_patient.html', questions=questions)


@app.route('/questions')
def questions():
    con = get_db()
    qs = con.execute('SELECT * FROM questions').fetchall()
    con.close()
    return render_template('questions.html', questions=qs)


@app.route('/questions/add', methods=['POST'])
def add_question():
    text = request.form['text']
    con = get_db()
    con.execute('INSERT INTO questions (text) VALUES (?)', (text,))
    con.commit()
    con.close()
    return redirect(url_for('questions'))


@app.route('/questions/delete/<int:qid>', methods=['POST'])
def del_question(qid):
    con = get_db()
    con.execute('DELETE FROM questions WHERE id=?', (qid,))
    con.commit()
    con.close()
    return redirect(url_for('questions'))


@app.route('/foods')
def foods():
    back = request.args.get('back', '/')
    con = get_db()
    fs = con.execute('SELECT * FROM foods ORDER BY name COLLATE NOCASE').fetchall()
    con.close()
    return render_template('foods.html', foods=fs, back=back)


@app.route('/foods/add', methods=['POST'])
def add_food():
    back = request.form.get('back')
    con = get_db()
    con.execute('INSERT INTO foods (name, kcal, carbs, protein, fat) VALUES (?,?,?,?,?)',
                (request.form['name'], request.form.get('kcal'), request.form.get('carbs'),
                 request.form.get('protein'), request.form.get('fat')))
    con.commit()
    con.close()
    if back:
        return redirect(url_for('foods', back=back))
    return redirect(url_for('foods'))


@app.route('/foods/delete/<int:fid>', methods=['POST'])
def del_food(fid):
    back = request.form.get('back')
    con = get_db()
    con.execute('DELETE FROM foods WHERE id=?', (fid,))
    con.commit()
    con.close()
    if back:
        return redirect(url_for('foods', back=back))
    return redirect(url_for('foods'))


@app.route('/patient/<int:pid>')
def patient_detail(pid):
    vid = request.args.get('visit')
    con = get_db()
    patient = con.execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()
    visits = con.execute('SELECT * FROM visits WHERE patient_id=? ORDER BY date DESC', (pid,)).fetchall()
    measures = con.execute('SELECT date, weight, waist, hip, height, navel, custom FROM visits WHERE patient_id=? ORDER BY date', (pid,)).fetchall()
    goals = con.execute('SELECT * FROM obiettivi WHERE patient_id=?', (pid,)).fetchone()
    goals_grams = None
    if goals:
        goals_grams = {
            'calories': goals['calories'],
            'cho_g': goals['calories'] * goals['cho_percent'] / 100 / 4,
            'pro_g': goals['calories'] * goals['pro_percent'] / 100 / 4,
            'fat_g': goals['calories'] * goals['fat_percent'] / 100 / 9,
            'cho_percent': goals['cho_percent'],
            'pro_percent': goals['pro_percent'],
            'fat_percent': goals['fat_percent'],
        }
    visit = None
    if vid:
        visit = con.execute('SELECT * FROM visits WHERE id=?', (vid,)).fetchone()
    con.close()
    return render_template('patient_detail.html', patient=patient, visits=visits,
                           visit=visit, measures=measures, goals=goals)


@app.route('/patient/<int:pid>/visit', methods=['GET', 'POST'])
def new_visit(pid):
    con = get_db()
    patient = con.execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()
    last = con.execute('SELECT notes FROM visits WHERE patient_id=? ORDER BY date DESC LIMIT 1', (pid,)).fetchone()
    last_notes = last['notes'] if last else ''
    if request.method == 'POST':
        vdate = request.form.get('date') or date.today().isoformat()
        weight = request.form.get('weight')
        waist = request.form.get('waist')
        hip = request.form.get('hip')
        height = request.form.get('height')
        navel = request.form.get('navel')
        custom = request.form.get('custom')
        notes = []
        idx = 1
        while True:
            title = request.form.get(f'title{idx}')
            desc = request.form.get(f'desc{idx}')
            if not title and not desc:
                break
            if title or desc:
                notes.append(f"<b>{title}</b> {desc}")
            idx += 1
        notes_str = '<br>'.join(notes)
        con.execute('INSERT INTO visits (patient_id, date, notes, weight, waist, hip, height, navel, custom) VALUES (?,?,?,?,?,?,?,?,?)',
                    (pid, vdate, notes_str, weight, waist, hip, height, navel, custom))
        con.commit()
        con.close()
        return redirect(url_for('patient_detail', pid=pid))
    con.close()
    return render_template('visit_form.html', today=date.today().isoformat(), last_notes=last_notes, patient=patient, visit=None, notes=None)




@app.route('/patient/<int:pid>/visit/<int:vid>/edit', methods=['GET', 'POST'])
def edit_visit(pid, vid):
    con = get_db()
    patient = con.execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()
    if request.method == 'POST':
        vdate = request.form.get('date') or date.today().isoformat()
        weight = request.form.get('weight')
        waist = request.form.get('waist')
        hip = request.form.get('hip')
        height = request.form.get('height')
        navel = request.form.get('navel')
        custom = request.form.get('custom')
        notes = []
        idx = 1
        while True:
            title = request.form.get(f'title{idx}')
            desc = request.form.get(f'desc{idx}')
            if not title and not desc:
                break
            if title or desc:
                notes.append(f"<b>{title}</b> {desc}")
            idx += 1
        notes_str = '<br>'.join(notes)
        con.execute('''UPDATE visits SET date=?, notes=?, weight=?, waist=?, hip=?, height=?, navel=?, custom=? WHERE id=?''',
                    (vdate, notes_str, weight, waist, hip, height, navel, custom, vid))
        con.commit()
        con.close()
        return redirect(url_for('patient_detail', pid=pid, visit=vid))
    visit = con.execute('SELECT * FROM visits WHERE id=?', (vid,)).fetchone()
    last = con.execute('SELECT notes FROM visits WHERE patient_id=? AND id!=? ORDER BY date DESC LIMIT 1',
                       (pid, vid)).fetchone()
    last_notes = last['notes'] if last else ''
    notes_list = parse_notes(visit['notes'])
    con.close()
    return render_template('visit_form.html', today=visit['date'], last_notes=last_notes,
                           patient=patient, visit=visit, notes=notes_list)


@app.route('/visit/<int:vid>/delete', methods=['POST'])
def delete_visit(vid):
    con = get_db()
    row = con.execute('SELECT patient_id FROM visits WHERE id=?', (vid,)).fetchone()
    pid = row['patient_id'] if row else None
    if row:
        con.execute('DELETE FROM visits WHERE id=?', (vid,))
        con.commit()
    con.close()
    if pid:
        return redirect(url_for('patient_detail', pid=pid))
    return redirect(url_for('index'))


@app.route('/patient/<int:pid>/goals', methods=['GET', 'POST'])
def edit_goals(pid):
    con = get_db()
    if request.method == 'POST':
        calories = request.form.get('calories')
        cho = request.form.get('cho_percent')
        pro = request.form.get('pro_percent')
        fat = request.form.get('fat_percent')
        if con.execute('SELECT id FROM obiettivi WHERE patient_id=?', (pid,)).fetchone():
            con.execute('''UPDATE obiettivi SET calories=?, cho_percent=?, pro_percent=?, fat_percent=?
                           WHERE patient_id=?''',
                        (calories, cho, pro, fat, pid))
        else:
            con.execute('''INSERT INTO obiettivi (patient_id, calories, cho_percent, pro_percent, fat_percent)
                           VALUES (?,?,?,?,?)''', (pid, calories, cho, pro, fat))
        con.commit()
        con.close()
        return redirect(url_for('patient_detail', pid=pid))
    goals = con.execute('SELECT * FROM obiettivi WHERE patient_id=?', (pid,)).fetchone()
    con.close()
    return render_template('goals_form.html', patient_id=pid, goals=goals)


DAYS = [f'Giorno{i}' for i in range(1, 8)]
MEALS = ['Colazione', 'Spuntino', 'Pranzo', 'Merenda', 'Cena']


@app.route('/patient/<int:pid>/meal_plan', methods=['GET', 'POST'])
def meal_plan(pid):
    con = get_db()
    patient = con.execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()
    foods = con.execute('SELECT * FROM foods ORDER BY name COLLATE NOCASE').fetchall()
    goals_row = con.execute('SELECT * FROM obiettivi WHERE patient_id=?', (pid,)).fetchone()
    goals_grams = None
    if goals_row:
        goals_grams = {
            'calories': goals_row['calories'],
            'cho_g': goals_row['calories'] * goals_row['cho_percent'] / 100 / 4,
            'pro_g': goals_row['calories'] * goals_row['pro_percent'] / 100 / 4,
            'fat_g': goals_row['calories'] * goals_row['fat_percent'] / 100 / 9,
            'cho_percent': goals_row['cho_percent'],
            'pro_percent': goals_row['pro_percent'],
            'fat_percent': goals_row['fat_percent'],
        }
    if request.method == 'POST':
        for day in DAYS:
            for meal in MEALS:
                fids = request.form.getlist(f'food_{day}_{meal}[]')
                grams_list = request.form.getlist(f'gram_{day}_{meal}[]')
                for fid, grams in zip(fids, grams_list):
                    if fid and grams:
                        con.execute('INSERT INTO meal_plans (patient_id, food_id, grams, day, meal) VALUES (?,?,?,?,?)',
                                    (pid, fid, grams, day, meal))
        con.commit()
    # read existing plan
    plan = {(d, m): [] for d in DAYS for m in MEALS}
    summary = {d: {'kcal':0,'carbs':0,'protein':0,'fat':0,
                    'meals':{m:{'kcal':0,'carbs':0,'protein':0,'fat':0} for m in MEALS}}
              for d in DAYS}
    rows = con.execute('''SELECT meal_plans.*, foods.name,
                           foods.kcal * meal_plans.grams / 100 AS kcal,
                           foods.carbs * meal_plans.grams / 100 AS carbs,
                           foods.protein * meal_plans.grams / 100 AS protein,
                           foods.fat * meal_plans.grams / 100 AS fat
                           FROM meal_plans JOIN foods ON meal_plans.food_id = foods.id
                           WHERE patient_id=?''', (pid,)).fetchall()
    for r in rows:
        plan[(r['day'], r['meal'])].append(r)
        d = summary[r['day']]
        m = d['meals'][r['meal']]
        for key in ('kcal','carbs','protein','fat'):
            d[key] += r[key]
            m[key] += r[key]
    con.close()
    foods_url = url_for('foods', back=url_for('meal_plan', pid=pid))
    return render_template('meal_plan.html', patient=patient, days=DAYS, meals=MEALS,
                           foods=foods, plan=plan, goals=goals_grams, summary=summary,
                           foods_url=foods_url)


@app.route('/patient/<int:pid>/meal_plan/delete/<int:mid>', methods=['POST'])
def delete_meal_item(pid, mid):
    con = get_db()
    con.execute('DELETE FROM meal_plans WHERE id=?', (mid,))
    con.commit()
    con.close()
    return redirect(url_for('meal_plan', pid=pid))


@app.route('/patient/<int:pid>/meal_plan/edit/<int:mid>', methods=['GET', 'POST'])
def edit_meal_item(pid, mid):
    con = get_db()
    if request.method == 'POST':
        food_id = request.form.get('food_id')
        grams = request.form.get('grams')
        con.execute('UPDATE meal_plans SET food_id=?, grams=? WHERE id=?', (food_id, grams, mid))
        con.commit()
        con.close()
        return redirect(url_for('meal_plan', pid=pid))
    foods = con.execute('SELECT * FROM foods ORDER BY name COLLATE NOCASE').fetchall()
    row = con.execute('SELECT * FROM meal_plans WHERE id=?', (mid,)).fetchone()
    con.close()
    return render_template('meal_item_form.html', patient_id=pid, row=row, foods=foods)


@app.route('/patient/<int:pid>/attachments', methods=['GET', 'POST'])
def patient_attachments(pid):
    con = get_db()
    patient = con.execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            pdir = os.path.join(ATTACH_FOLDER, str(pid))
            os.makedirs(pdir, exist_ok=True)
            fname = secure_filename(file.filename)
            unique = f"{int(time.time())}_{fname}"
            path = os.path.join(pdir, unique)
            file.save(path)
            rel = os.path.relpath(path, ATTACH_FOLDER)
            # Use forward slashes so send_from_directory works on all OSes
            rel = rel.replace(os.sep, '/')
            con.execute('INSERT INTO attachments (patient_id, filename, filepath) VALUES (?,?,?)',
                        (pid, fname, rel))
            con.commit()
        con.close()
        return redirect(url_for('patient_attachments', pid=pid))
    attachments = con.execute('SELECT * FROM attachments WHERE patient_id=?', (pid,)).fetchall()
    con.close()
    return render_template('attachments.html', patient=patient, attachments=attachments)


@app.route('/attachments/download/<int:aid>')
def download_attachment(aid):
    con = get_db()
    row = con.execute('SELECT filepath, filename FROM attachments WHERE id=?', (aid,)).fetchone()
    con.close()
    if row:
        filepath = row['filepath'].replace('\\', '/')
        try:
            return send_from_directory(ATTACH_FOLDER, filepath, as_attachment=True, download_name=row['filename'])
        except TypeError:
            # Compatibility with older Flask versions
            return send_from_directory(ATTACH_FOLDER, filepath, as_attachment=True, attachment_filename=row['filename'])
    return 'Not found', 404


@app.route('/attachments/delete/<int:aid>', methods=['POST'])
def delete_attachment(aid):
    con = get_db()
    row = con.execute('SELECT filepath, patient_id FROM attachments WHERE id=?', (aid,)).fetchone()
    pid = None
    if row:
        pid = row['patient_id']
        fpath = os.path.join(ATTACH_FOLDER, row['filepath'].replace('/', os.sep))
        try:
            os.remove(fpath)
        except FileNotFoundError:
            pass
        con.execute('DELETE FROM attachments WHERE id=?', (aid,))
        con.commit()
    con.close()
    if pid:
        return redirect(url_for('patient_attachments', pid=pid))
    return redirect(url_for('index'))


@app.route('/patient/<int:pid>/edit', methods=['GET', 'POST'])
def edit_patient(pid):
    con = get_db()
    patient = con.execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()
    if not patient:
        con.close()
        return redirect(url_for('index'))
    if request.method == 'POST':
        con.execute('''UPDATE patients SET name=?, birthdate=?, email=?, phone=?, fiscal_code=? WHERE id=?''',
                    (request.form['name'], request.form.get('birthdate'), request.form.get('email'),
                     request.form.get('phone'), request.form.get('fiscal_code'), pid))
        con.commit()
        con.close()
        return redirect(url_for('patient_detail', pid=pid))
    con.close()
    return render_template('edit_patient.html', patient=patient)


@app.route('/patient/<int:pid>/delete', methods=['GET', 'POST'])
def delete_patient(pid):
    con = get_db()
    patient = con.execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()
    if not patient:
        con.close()
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        name_entered = request.form.get('confirm_name', '').strip().lower()
        if name_entered == patient['name'].strip().lower():
            attach_rows = con.execute('SELECT filepath FROM attachments WHERE patient_id=?', (pid,)).fetchall()
            for row in attach_rows:
                fpath = os.path.join(ATTACH_FOLDER, row['filepath'].replace('/', os.sep))
                try:
                    os.remove(fpath)
                except FileNotFoundError:
                    pass
            con.execute('DELETE FROM attachments WHERE patient_id=?', (pid,))
            con.execute('DELETE FROM visits WHERE patient_id=?', (pid,))
            con.execute('DELETE FROM meal_plans WHERE patient_id=?', (pid,))
            con.execute('DELETE FROM obiettivi WHERE patient_id=?', (pid,))
            con.execute('DELETE FROM patients WHERE id=?', (pid,))
            con.commit()
            con.close()
            return redirect(url_for('index'))
        else:
            error = 'Nome non corrispondente'
    con.close()
    return render_template('patient_delete_confirm.html', patient=patient, error=error)


if __name__ == '__main__':
    if not verify_license():
        raise SystemExit('Licenza non valida.')
    init_db()

    def open_browser():
        webbrowser.open_new('http://127.0.0.1:5000/')

    threading.Timer(1.0, open_browser).start()
    app.run(debug=False)
