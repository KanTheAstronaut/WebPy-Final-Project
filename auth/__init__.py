from __future__ import annotations
import base64
from datetime import datetime # allow referecing types before they are added for type hinting
from os import getenv, mkdir, path
import sqlite3
import bcrypt
from bson import ObjectId
from dotenv import load_dotenv
from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from flask_wtf import FlaskForm
import gridfs
from pymongo import MongoClient
from wtforms import EmailField, PasswordField, RadioField, StringField, SubmitField
from wtforms.validators import DataRequired, Length
from mongolib.object import MongoObject
from flask_mail import Message
from flask_babel import gettext
from flask_wtf.file import FileField, FileAllowed
from werkzeug.utils import secure_filename

# load all environment variables from the .env file
load_dotenv()

instancepath = ''
try:
    instancepath = g.instance_path
except:
    pass

mail = g.mail

def getSQLiteDB():
    sqlDB = getattr(g, '_database', None)
    if sqlDB is None:
        sqlDB = g._database = sqlite3.connect("drivers.db")
        createSQLiteTable(sqlDB)
    return sqlDB

# this will create the table users in our sqlite db
def createSQLiteTable(sqlDB):
    cursor = sqlDB.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS drivers (
                   userId VARCHAR(20) PRIMARY KEY,
                   carType TEXT,
                     carMake TEXT,
                        carModel TEXT,
                        carYear TEXT,
                        carColor TEXT,
                        carLicensePlate TEXT)""")
    sqlDB.commit()

# create the mongo client from the connection string in the .env file
mongo = MongoClient(getenv("MONGO_URI"))
db = mongo["mainDatabase"]
users = db['users']
rides = db['rides']

fs = gridfs.GridFS(db)

auth_blueprint = Blueprint('auth', __name__,
                        template_folder='templates')

def logThemIn(user: User) -> None:
    # notify the user that a new login occurred
    msg = Message(subject="New login from your account!", body="Hello! You logged in at " + str(datetime.now()),
                  sender="no-reply@company.com",
                  recipients=[user.email])
    mail.send(msg)
    login_user(user)

class User(MongoObject, UserMixin):
    def __init__(self, id: str, username: str, password: str, email: str, driver: bool, imageId: str):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.driver = driver
        self.imageId = imageId
        if (self.id is None): # Creates a user instance and inserts it into mongodb (also hashes the password)
            self.password = bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            self.id = str(users.insert_one(self.MongoSafeObject()).inserted_id)
    
    @property
    def image(self) -> str|None:
        binary = fs.find_one({"image_id": self.imageId}).read()
        return base64.b64encode(binary).decode('utf-8') if binary is not None else None

    # Verify if a password matches the current instance's password hash
    def MatchPasswordHash(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

    # Get user by id (also used by flask-login)
    @g.login_manager.user_loader
    def GetUserById(userid: str) -> User|None:
        user = users.find_one({'_id': ObjectId(userid)})
        userObj = User.convertBack(user) if user is not None else None
        if (userObj is None):
            return None
        
        if (userObj.driver):
            return Driver.GetDriver(userObj)
        else:
            return userObj
    
    def GetUserByUsername(username: str) -> User|None:
        user = users.find_one({'username': username})
        return User.convertBack(user) if user is not None else None
    
    def GetUsers() -> list[User]:
        return [User.convertBack(user) for user in users.find({})]

    def Update(self):
        users.update_one({"_id": ObjectId(self.id)}, {"$set": self.MongoSafeObject()})

    def IsUsernameTaken(username: str) -> bool:
        return User.GetUserByUsername(username = username) is not None
    
    def GetDriver(self) -> Driver|None:
        if (self.driver):
            Driver.GetDriver(self)
        return None
    
    def CreateDriver(self, carType: str, carMake: str, carModel: str, carYear: str, carColor: str, carLicensePlate: str) -> Driver:
        conn = getSQLiteDB()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO drivers VALUES (?, ?, ?, ?, ?, ?, ?)', (self.id, carType, carMake, carModel, carYear, carColor, carLicensePlate))
        conn.commit()
        return Driver.GetDriver(self)
    
class Driver(User):
    def FindDriver(vehicleType: str) -> Driver|None:
        conn = getSQLiteDB()
        cursor = conn.cursor()
        cursor.execute('SELECT userId, carType FROM drivers WHERE carType = ?', (vehicleType,))

        drivers = cursor.fetchall()
        freeDriver = None
        for i in drivers:
            if (rides.find_one({"driverId": i[0]}) is not None):
                continue
            freeDriver = Driver.GetDriver(User.GetUserById(i[0]))
        
        return freeDriver

    def GetDriver(user: User) -> Driver|None:
        conn = getSQLiteDB()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM drivers WHERE userId = ?', (user.id,))

        driver = cursor.fetchone()
        if (driver is None):
            return None
        
        return Driver(driver[1], driver[2], driver[3], driver[4], driver[5], driver[6], user.id, user.username, user.password, user.email, user.driver, user.imageId)
    
    def __init__(self, carType: str, carMake: str, carModel: str, carYear: str, carColor: str, carLicensePlate: str, id: str, username: str, password: str, email: str, driver: bool, imageId: str):
        super().__init__(id, username, password, email, driver, imageId)
        self.carType = carType
        self.carMake = carMake
        self.carModel = carModel
        self.carYear = carYear
        self.carColor = carColor
        self.carLicensePlate = carLicensePlate

    def UpdateDriver(self):
        conn = getSQLiteDB()
        cursor = conn.cursor()
        cursor.execute('UPDATE drivers SET carType=?, carMake=?, carModel=?, carYear=?, carColor=?, carLicensePlate=? WHERE userId=?', (self.carType, self.carMake, self.carModel, self.carYear, self.carColor, self.carLicensePlate, self.id))
        conn.commit()

class LoginForm(FlaskForm):
    username = StringField(gettext('Username'), validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField(gettext('Password'), validators=[DataRequired(), Length(min=3, max=128)])
    submit = SubmitField(gettext('Login'))

class RegistrationForm(FlaskForm):
    email = EmailField(gettext('Email'), validators=[DataRequired(), Length(min=4, max=350)])
    username = StringField(gettext('Username'), validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField(gettext('Password'), validators=[DataRequired(), Length(min=3, max=128)])
    image = FileField(gettext('Profile Image'), validators=[FileAllowed(['jpg', 'png', 'jpeg'], gettext('Images only!'))])
    accountType = RadioField(gettext('Type'), validators=[DataRequired()], choices=[('rider','Looking for a ride'),('driver','Looking to offer rides')])
    submit = SubmitField(gettext('Register'))

class DriverInformationForm(FlaskForm):
    carType = StringField(gettext('Car Type'), validators=[DataRequired(), Length(min=3, max=64)])
    carMake = StringField(gettext('Car Make'), validators=[DataRequired(), Length(min=3, max=64)])
    carModel = StringField(gettext('Car Model'), validators=[DataRequired(), Length(min=3, max=64)])
    carYear = StringField(gettext('Car Year'), validators=[DataRequired(), Length(min=3, max=64)])
    carColor = StringField(gettext('Car Color'), validators=[DataRequired(), Length(min=3, max=64)])
    carLicensePlate = StringField(gettext('Car License Plate'), validators=[DataRequired(), Length(min=3, max=64)])
    submit = SubmitField(gettext('Submit'))

#region credentials
@auth_blueprint.route('/logout')
def logout():
    logout_user()
    return redirect('/')

@auth_blueprint.route('/admin', methods=['GET', 'POST'])
def admin():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        if bcrypt.checkpw(password.encode('utf-8'), getenv('adminPassword').encode('utf-8')) and username == "admin":
            return render_template('admin.html', users=User.GetUsers())
        else:
            flash(gettext('Invalid username or password'), 'error')
    return render_template('login.html', form=form)
    
@auth_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect('/')

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.GetUserByUsername(username = username)
        
        if user and user.MatchPasswordHash(password):
            if (user.driver):
                driver = Driver.GetDriver(user)
                if (driver is None):
                    logThemIn(user)
                    return redirect(url_for('auth.initialDriver'))
                else:
                    user = driver
            logThemIn(user)
            next = request.form.get('next') # get the next attribute (which defines where the user was attempting to visit before they were forced to authenticate)
            return redirect(next if next is not None else '/') # if the next url isnt null redirect them there otherwise default to the home page
        else:
            # dont tell the user which one is incorrect for security/privacy reasons
            flash(gettext('Invalid username or password'), 'error')
    return render_template('login.html', form=form)

@auth_blueprint.route('/initialDriver', methods=['GET', 'POST'])
@login_required
def initialDriver():
    if not current_user.driver:
        return redirect('/')
    form = DriverInformationForm()
    if form.validate_on_submit():
        driver = User.CreateDriver(current_user, form.carType.data.lower(), form.carMake.data, form.carModel.data, form.carYear.data, form.carColor.data, form.carLicensePlate.data)
        login_user(driver, force = True)
        return redirect('/')
    return render_template('driverInformation.html', form=form)

@auth_blueprint.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect('/')

    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data
        username = form.username.data
        password = form.password.data
        driver = form.accountType.data == 'driver'

        if not User.IsUsernameTaken(username):
            imageId = None
            if (form.image.data is not None):
                imageId = str(ObjectId())
                image = form.image.data
                filename = secure_filename(image.filename)
                fs.put(image, filename=filename, image_id=imageId)

            user = User(None, username, password, email, driver, imageId)
            # automatically log the user in so they dont have to login after signing up
            logThemIn(user)
            if (user.driver):
                return redirect(url_for('auth.initialDriver')) # redirect the driver so they can set their vehicle information
            # for the first time
            next = request.form.get('next') # get the next attribute (which defines where the user was attempting to visit before they were forced to authenticate)
            return redirect(next if next is not None else '/') # if the next url isnt null redirect them there otherwise default to the home page
        else:
            flash(gettext('Username is not available!'), 'error')
    return render_template('signup.html', form=form)
#endregion
