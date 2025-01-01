from flask import Flask, render_template, request, redirect, url_for
import json
import unicodedata
import re
from difflib import SequenceMatcher
from flask_pymongo import MongoClient
from dotenv import load_dotenv
import os
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from bson.objectid import ObjectId
from ast import literal_eval

load_dotenv()
 
app = Flask(__name__)
app.secret_key = "super secret key"
app.config['SECRET_KEY'] = 'your_secret_key'    

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

client = MongoClient(os.getenv("DATABASE_URL"))

db = client["books"]
collection_books = db["books"]
collection_user = db["user"]

def add(dic):
    result = collection_books.insert_one(dic)   
    update = collection_user.update_one({"_id": ObjectId(dic["userFor"])}, {"$push": {"mybooks": result.inserted_id}}, )


def delete(id):
    result = collection_books.delete_one({"_id": ObjectId(id)})
    update = collection_user.update_one({"_id": ObjectId(current_user.get_id())}, {"$pull": {"mybooks": ObjectId(id)}} )
    return(collection_user.find_one({"_id": ObjectId(current_user.get_id())}))

def edit(id, new):
    for i in new: 
        result = collection_books.update_one({"_id": ObjectId(id)}, {"$set": {i: new[i]}})

def openJSON(ids):
    c=[]
    for i in range(len(ids)):
        a = collection_books.find_one({'_id': ObjectId(ids[i])})
        a["_id"] = str(a["_id"])
        c.append(a)
    return c


def norm(x):
    x = unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode('utf-8')
    x = re.sub(r'[^\w\s]', " ", x)
    x = ' '.join(x.split()).lower()
    return(x) 


def search(x, y):
    norm_x = norm(x)
    norm_y = norm(y)

    split_x = norm_x.split()
    split_y = norm_y.split()

    correspondances = []
    for m in split_y:
        correspondances.append(any(m in i for i in split_x))
    
    return all(correspondances)

def search_cards(y, data):
    books = openJSON(data)
    results = []
    for i in range(len(books)):
        somme = " ".join([books[i]["name"], books[i]["author"]])
        if search(somme, y) :
            results.append(books[i])
    return results

class User(UserMixin):
    def __init__(self, user_id, username, mybooks, question, answer):
        self.id = user_id
        self.username = username
        self.mybooks = mybooks
        self.question = question
        self.answer = answer

@login_manager.user_loader
def load_user(user_id):
    user_data = collection_user.find_one({'_id': ObjectId(user_id)})    
    if user_data:
        return User(user_id=user_data['_id'], username=user_data['username'], mybooks=user_data['mybooks'], question=user_data['question'], answer=user_data['answer'])
    return None


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route('/search', methods=["POST"])
def searchREQ():
    v = request.get_json()["value"]
    d = request.get_json()["data"]
    if type(d) != list :
        finalD = json.loads(d)
    else:
        finalD = d
    ids = []
    for bo in finalD:
        ids.append(bo["_id"])
    if(v != ""):
        results = search_cards(v, ids)
        return results
    else : 
        return d
    
@app.route('/filterByWish', methods=["POST"])
def filterREQ():
    d = request.get_json()["data"]
    if type(d) != list :
        finalD = json.loads(d)
    else:
        finalD = d
    results = []
    for bo in finalD:
        if not bo["gotIt"]:
            results.append(bo)
    return results

@app.route("/list", methods=['GET', 'POST'])
@login_required
# python -m flask --app app --debug run
def hello_world():
    data = openJSON(current_user.mybooks)
    r=[]   
    for i in range(len(data)):
        if data[i]["accepted"]:
            r.append(data[i])
    return render_template('list.html', result = r)

@app.route("/wish", methods=['GET', 'POST'])
@login_required
# python -m flask --app app --debug run
def wish():
    data = openJSON(current_user.mybooks)
    r=[]   
    idé=[]   
    for i in range(len(data)):
        if data[i]["accepted"] and not data[i]["gotIt"]:
            r.append(data[i])
            idé.append(data[i]["_id"])
    return render_template('list.html', result = r)

@app.route("/add", methods=['GET', 'POST'])
@login_required
def addPage():
    if request.method == 'POST':
        name = request.form.get('name')
        img = request.form.get('img')
        author = request.form.get('author')
        gotIt = bool(request.form.get('gotIt'))
        prev = request.form.get('previous')
        dic = {"name": name,"author": author,"img": img,"gotIt": gotIt, "lien": "", "userFor": current_user.get_id(), "userFrom": "", "accepted": True}
        add(dic)
        return redirect(prev)

@app.route("/edit", methods=['GET', 'POST'])
@login_required
def editPage():
    cards = openJSON(current_user.mybooks) 
    if request.method == "POST":
        user = request.args.get('q')
        dic = {}
        dic["gotIt"] = bool(request.form.get('gotIt'))
        dic["name"] = request.form.get('name')
        dic["author"] = request.form.get('author')
        dic["img"] = request.form.get('img')
        prev = request.form.get('previous')
        for i in range(len(cards)):
            if(cards[i]["_id"] == user):
                edit(cards[i]["_id"], dic)
        return redirect(prev)
    

@app.route("/delete", methods=['POST'])
def deletePage(): 
    cards = openJSON(current_user.mybooks) 
    cardN = request.args.get('q') 
    for i in range(len(cards)):
        if(str(cards[i]["_id"]) == cardN):
            a = delete(cards[i]["_id"])
    return

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        question = request.form['question']
        answer = request.form['answer']
        existing_user = collection_user.find_one({'username': username})

        if existing_user:
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        collection_user.insert_one({'username': username, 'password': hashed_password, 'mybooks' : [], "question": question, "answer":answer})
        return redirect(url_for('login')) 
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = collection_user.find_one({'username': username})

        if user_data and bcrypt.check_password_hash(user_data['password'], password):
            user = User(user_id=user_data['_id'], username=user_data['username'], mybooks=user_data['mybooks'], answer=user_data['answer'], question=user_data['question'])
            login_user(user)
            return redirect(url_for('hello_world'))
    return render_template('login.html')


@app.route("/submit", methods=['GET', 'POST'])
@login_required
def submitcard():
    if request.method == 'POST':
        name = request.form.get('name')
        img = request.form.get('img')
        author = request.form.get('author')
        description = request.form.get('description')
        userfor = request.form.get('userfor')
        dic = {"name": name,"author": author,"img": img,"gotIt": False, "description": description, "lien": "", "userFor": userfor, "userFrom": current_user.username, "accepted": False}
        add(dic)
    c=[]
    a = collection_user.find()
    for b in a:
        if(str(b["_id"]) != current_user.get_id()):
            b["_id"] = str(b["_id"])
            c.append(b)
    return render_template('submit.html', users = c)

@app.route("/logout", methods=['GET', 'POST'])
@login_required
def logout():
    if request.method == "POST":
        logout_user()
        return redirect(url_for('hello_world'))
    return render_template('logout.html')

@app.route("/forget", methods=['GET', 'POST'])
def forget(): 
    if request.method == "POST":
        username = request.form['username']
        question = request.form['question']
        answer = request.form['answer']
        existing_user = collection_user.find_one({'username': username})
        if existing_user and existing_user['question'] == question and existing_user['answer'] == answer:
            new_id = str(existing_user['_id'])
            return redirect(url_for('pwd', user=new_id))

    return render_template('forget.html')

@app.route("/new-pwd", methods=['GET', 'POST'])
def pwd(): 
    existing = request.args.get('user') 

    if request.method == "POST":
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        update = collection_user.update_one({'_id': ObjectId(existing)}, {"$set": {"password": hashed_password}})
        return redirect(url_for("login"))
    return render_template('pwd.html', data=existing)

@app.route("/propositions", methods=['GET', 'POST'])
@login_required
def choices():
    if request.method == 'POST':
        user = request.args.get('q')
        dic = {"accepted": True}
        edit(user, dic)
    data = openJSON(current_user.mybooks)
    r=[]
    for i in range(len(data)):
        if not data[i]["accepted"]:
            r.append(data[i]) 
    return render_template('choices.html', results = r)  

@app.route("/choose-user", methods=['GET', "POST"])
def choix():
    if request.method == 'POST':
        user = request.form['user']
        print(user)
        return redirect(url_for("other", user=user))

    ds = collection_user.find()
    result = []
    for d in ds:
        if current_user.is_authenticated:
            if(str(d['_id']) != current_user.get_id()):
               result.append(d)
        else:
            result.append(d)
    return render_template("userchooser.html", data = result)

@app.route("/other", methods=['GET', 'POST'])
def other():
    existing = request.args.get('user') 
    e = collection_user.find_one({'_id': ObjectId(existing)})
    data = openJSON(e['mybooks'])
    r=[]   
    for i in range(len(data)):
        if data[i]["accepted"]:
            r.append(data[i])
            
    return render_template('other.html', result = r)