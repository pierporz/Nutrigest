import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from datetime import date

app = Flask(__name__)
DB = 'nutrigest.db'


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with open('init_db.sql') as f:
        sql = f.read()
    conn = get_db()
    conn.executescript(sql)
    conn.commit()
    conn.close()




@app.route('/')
def index():
    con = get_db()
    patients = con.execute('SELECT * FROM patients').fetchall()
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
        cur.execute('INSERT INTO visits (patient_id, date, notes, weight, waist, hip) VALUES (?,?,?,?,?,?)',
                    (pid, date.today(), notes, weight, waist, hip))
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
    con = get_db()
    fs = con.execute('SELECT * FROM foods').fetchall()
    con.close()
    return render_template('foods.html', foods=fs)


@app.route('/foods/add', methods=['POST'])
def add_food():
    con = get_db()
    con.execute('INSERT INTO foods (name, kcal, carbs, protein, fat) VALUES (?,?,?,?,?)',
                (request.form['name'], request.form.get('kcal'), request.form.get('carbs'),
                 request.form.get('protein'), request.form.get('fat')))
    con.commit()
    con.close()
    return redirect(url_for('foods'))


@app.route('/foods/delete/<int:fid>', methods=['POST'])
def del_food(fid):
    con = get_db()
    con.execute('DELETE FROM foods WHERE id=?', (fid,))
    con.commit()
    con.close()
    return redirect(url_for('foods'))


@app.route('/patient/<int:pid>')
def patient_detail(pid):
    vid = request.args.get('visit')
    edit = request.args.get('edit')
    con = get_db()
    patient = con.execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()
    visits = con.execute('SELECT * FROM visits WHERE patient_id=? ORDER BY date DESC', (pid,)).fetchall()
    measures = con.execute('SELECT date, weight, waist, hip FROM visits WHERE patient_id=? ORDER BY date', (pid,)).fetchall()
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
                           visit=visit, measures=measures, goals=goals, edit=edit)


@app.route('/patient/<int:pid>/visit', methods=['GET', 'POST'])
def new_visit(pid):
    con = get_db()
    last = con.execute('SELECT notes FROM visits WHERE patient_id=? ORDER BY date DESC LIMIT 1', (pid,)).fetchone()
    last_notes = last['notes'] if last else ''
    if request.method == 'POST':
        vdate = request.form.get('date') or date.today().isoformat()
        weight = request.form.get('weight')
        waist = request.form.get('waist')
        hip = request.form.get('hip')
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
        con.execute('INSERT INTO visits (patient_id, date, notes, weight, waist, hip) VALUES (?,?,?,?,?,?)',
                    (pid, vdate, notes_str, weight, waist, hip))
        con.commit()
        con.close()
        return redirect(url_for('patient_detail', pid=pid))
    con.close()
    return render_template('visit_form.html', today=date.today().isoformat(), last_notes=last_notes)




@app.route('/patient/<int:pid>/visit/<int:vid>/edit', methods=['POST'])
def edit_visit(pid, vid):
    notes = request.form['notes']
    con = get_db()
    con.execute('UPDATE visits SET notes=? WHERE id=?', (notes, vid))
    con.commit()
    con.close()
    return redirect(url_for('patient_detail', pid=pid, visit=vid))


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
    foods = con.execute('SELECT * FROM foods').fetchall()
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
    return render_template('meal_plan.html', patient=patient, days=DAYS, meals=MEALS,
                           foods=foods, plan=plan, goals=goals_grams, summary=summary)


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
    foods = con.execute('SELECT * FROM foods').fetchall()
    row = con.execute('SELECT * FROM meal_plans WHERE id=?', (mid,)).fetchone()
    con.close()
    return render_template('meal_item_form.html', patient_id=pid, row=row, foods=foods)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
