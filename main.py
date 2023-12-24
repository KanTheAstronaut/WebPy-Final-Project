from datetime import datetime
from gettext import gettext
import random
import sqlite3
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, flash, g, redirect, render_template, request
from flask_login import LoginManager, current_user, login_required
from flask_socketio import SocketIO, emit, join_room, Namespace
from pymongo import MongoClient
import requests
from flask_mail import Message
from flask_mail import Mail
from flask_babel import Babel
from os import getenv
from flask_wtf import FlaskForm
from wtforms import HiddenField, RadioField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired
import folium

from werkzeug import exceptions as HttpErrors # stores http error status codes in a readable way

app = Flask(__name__)

socketio = SocketIO(app)

load_dotenv()

app.config['MAIL_SERVER']='sandbox.smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USERNAME'] = getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

# randomize secret key for development (you will need to reauthenticate whenever you restart the server)
app.config['SECRET_KEY'] = 'test'#str(ObjectId())

mail = Mail(app)

babel = Babel(app)

app.config['LANGUAGES'] = {
    'en': 'English',
    'fr': 'French',
    'ar': 'Arabic'
}

# renaming this causes a lot of internal errors
login_manager = LoginManager()
login_manager.init_app(app)
# tell the login manager to use the login route to redirect users to when they try to access areas that require authentication
login_manager.login_view = 'auth.login'

mongo = MongoClient(getenv("MONGO_URI"))
db = mongo["mainDatabase"]
rides = db['rides']

def get_locale():
    try:
        return request.accept_languages.best_match(app.config['LANGUAGES'].keys())
    except:
        return 'en'

babel.init_app(app, locale_selector=get_locale)

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

# we need to use with app context because if we import from auth it will hit the line that uses "g" (in the auth module)
    # so we need to have already defined all of the g variables before referencing auth which we need the appcontext for
with app.app_context():
    g.mail = mail
    g.login_manager = login_manager
    g.babel = babel
    g.instance_path = app.instance_path
    from auth import Driver, User
    @app.route('/', methods=['GET', 'POST'])
    @login_required
    def index():
            if (current_user.driver):
                # a page for the driver to view all of their pending rides
                if (current_user.carType not in RideExchangeNamespace.pendingRideRequests):
                    RideExchangeNamespace.pendingRideRequests[current_user.carType] = []
                return render_template('driver.html', pendingRides=RideExchangeNamespace.pendingRideRequests[current_user.carType])
            else:
                form = RequestRide()
                conn = getSQLiteDB()
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT carType FROM drivers')
                form.vehicleType.choices = [(i[0], i[0]) for i in cursor.fetchall()]
                if form.validate_on_submit():
                    if (form.nowOrLater.data == "now" and (form.time.data is not None and form.time.data != "")):
                        flash("You can't define the time when you are requesting a ride for now!")
                    else:
                        driver = Driver.FindDriver(form.vehicleType.data)
                        # get the long/lat from a text address
                        base_url = 'https://nominatim.openstreetmap.org/search'

                        params = {
                            'q': form.address.data,
                            'format': 'json',
                        }

                        response = requests.get(base_url, params=params)
                        data = response.json()

                        if response.status_code == 200 and data:
                            location = data[0] # pick the first matching location
                            lat, lng = location['lat'], location['lon']
                            # create the ride request object so the page can broadcast it to all drivers
                            data = {'userId': current_user.id, 'address': { 'long': lng, 'lat': lat }, 'textAddress': form.address.data, 
                                'pickup': {'long': form.long.data, 'lat': form.lat.data},
                                'time': form.time.data if form.nowOrLater.data != "now" else 'now', 'id': current_user.id, 'carType': form.vehicleType.data
                            }
                            return render_template('waiting.html', data=data)
                        else:
                            flash("Invalid address!")
                return render_template('rider.html', form=form)

    # this route shows ride details
    @app.route('/ride/<rideId>')
    @login_required
    def rideDetails(rideId):
        ride = rides.find_one({'_id': ObjectId(rideId)})
        if (ride is None or (ride['driverId'] != current_user.id and ride['riderId'] != current_user.id)):
            return redirect('/')
        rider = User.GetUserById(ride['riderId'])
        driver = Driver.GetDriver(User.GetUserById(ride['driverId']))

        if (ride['arrived']):
            return redirect(f'/ride/{rideId}/invoice')

        # Define coordinates of points
        point_A = [float(ride['pickup']['long']), float(ride['pickup']['lat'])]
        point_B = [float(ride['address']['long']), float(ride['address']['lat'])]

        # Create the map
        map = folium.Map(location=point_B, zoom_start = 13)

        # Add points to the map
        folium.Marker(point_A, popup='Pickup').add_to(map)
        folium.Marker(point_B, popup='Destination').add_to(map)

        # Draw line between point A and point B
        folium.PolyLine(locations=[point_A, point_B], color="red", weight=2.5, opacity=1).add_to(map)

        return render_template('ride.html', ride=ride, rider=rider, driver=driver, map=map._repr_html_())

    # this route is for the ride chat page between the driver and the rider
    @app.route('/ride/<rideId>/chat')
    @login_required
    def rideChat(rideId):
        ride = rides.find_one({'_id': ObjectId(rideId)})
        if (ride is None or (ride['driverId'] != current_user.id and ride['riderId'] != current_user.id)):
            return redirect('/')
        rider = User.GetUserById(ride['riderId'])
        driver = Driver.GetDriver(User.GetUserById(ride['driverId']))
        return render_template('chat.html', messages=ride['chat'], ride=ride, rider=rider, driver=driver)

    # this route shows the driver and the rider the final invoice
    @app.route('/ride/<rideId>/invoice')
    @login_required
    def rideInvoice(rideId):
        ride = rides.find_one({'_id': ObjectId(rideId)})
        if (ride is None or (ride['driverId'] != current_user.id and ride['riderId'] != current_user.id) or not ride['arrived']):
            return redirect('/')
        rider = User.GetUserById(ride['riderId'])
        driver = Driver.GetDriver(User.GetUserById(ride['driverId']))
        return render_template('invoice.html', ride=ride, rider=rider, driver=driver, amountEarned=ride['cost'])

    class RideNamespace(Namespace):
        userSessionIds = {}
        @login_required
        def on_join(self, data):
            ride = rides.find_one({'_id': ObjectId(data['id'])})
            if (ride is None or (ride['driverId'] != current_user.id and ride['riderId'] != current_user.id)):
                emit('Failed', {'msg': 'Invalid ride!'})
                return
            join_room(data['id'])
            RideNamespace.userSessionIds[current_user.id] = request.sid

        @login_required
        def on_triggerarrived(self, data):
            ride = rides.find_one({'_id': ObjectId(data['id'])})
            if (ride is None or (ride['driverId'] != current_user.id)):
                return redirect('/')
            rider = User.GetUserById(ride['riderId'])
            amountEarned = random.randint(1, 100)
            rides.update_one({'_id': ObjectId(ride['_id'])}, {'$set': {'arrived': True, 'cost': amountEarned}})
            emit('refresh', room=ride['_id'], broadcast=True)
            msg = Message(subject="Ride completed!", body=f"Hello! You owe {amountEarned}$ to your driver!",
                        sender="no-reply@company.com",
                        recipients=[rider.email])
            mail.send(msg)

    class RideChatNamespace(Namespace):
        userSessionIds = {}
        @login_required
        def on_join(self, data):
            ride = rides.find_one({'_id': ObjectId(data['id'])})
            if (ride is None or (ride['driverId'] != current_user.id and ride['riderId'] != current_user.id)):
                emit('Failed', {'msg': 'Invalid ride!'})
                return
            join_room(data['id'])
            RideChatNamespace.userSessionIds[current_user.id] = request.sid
        
        # for notifying others that a message has been sent and store the message in the database
        @login_required
        def on_chat(self, data):
            ride = rides.find_one({'_id': ObjectId(data['id'])})
            if (ride is None or (ride['driverId'] != current_user.id and ride['riderId'] != current_user.id)):
                emit('Failed', {'msg': 'Invalid ride!'})
                return
            rides.update_one({'_id': ObjectId(data['id'])}, {'$push': {'chat': {'sender': 'driver' if current_user.driver else 'rider', 'message': data['message']}}})
            emit('refresh', room=data['id'], broadcast=True)

    class RideExchangeNamespace(Namespace):
        userSessionIds = {}
        pendingRideRequests = {}

        @login_required
        def on_join(self, data):
            # if the user is already in a ride (driver or rider) that doesnt have the "arrived" attribute then they cant join another ride
            if (current_user.driver and rides.find_one({"driverId": current_user.id, 'arrived': {'$exists': False}}) is not None):
                emit('Failed', {'msg': 'You are already in a ride!'})
                return
            elif (not current_user.driver and rides.find_one({"riderId": current_user.id, 'arrived': {'$exists': False}}) is not None):
                emit('Failed', {'msg': 'You are already in a ride!'})
                return
            # the room id for drivers is basically dependent on their car type
            join_room(f"{current_user.id}-WAITING" if not current_user.driver else f"{current_user.carType}-DECIDING")
            if (not current_user.driver):
                # create the ride request object
                rideRequest = {'userId': current_user.id, 'address': { 'long': data['address']['long'], 'lat': data['address']['lat'] }, 'textAddress': data['textAddress'], 
                                'pickup': {'long': data['pickup']['long'], 'lat': data['pickup']['lat']},
                                'time': data['time'] if 'time' in data else 'now', 'carType': data['carType']
                            }
                # notify all drivers that a new ride request has been made
                emit('giveride', rideRequest,
                    room=f"{data['carType']}-DECIDING", broadcast=True)
                # add the ride request to the list of pending ride requests (set a default list if one doesnt exist)
                if (data['carType'] not in RideExchangeNamespace.pendingRideRequests):
                    RideExchangeNamespace.pendingRideRequests[data['carType']] = []
                RideExchangeNamespace.pendingRideRequests[data['carType']].append(rideRequest)
            # store session ids just in case we need to communicate directly with someone
            RideExchangeNamespace.userSessionIds[current_user.id] = request.sid
        
        @login_required
        def on_cancel(self, _):
            if (current_user.driver):
                return
            for carType, rideRequestList in RideExchangeNamespace.pendingRideRequests:
                for rideRequest in rideRequestList:
                    if (rideRequest['userId'] == current_user.id):
                        RideExchangeNamespace.pendingRideRequests[carType].remove(rideRequest)
                        return

        @login_required
        def on_selrid(self, data):
            if (not current_user.driver):
                return
            userId = data['userId']
            carType = data['carType']
            for rideRequest in RideExchangeNamespace.pendingRideRequests[carType]:
                if (rideRequest['userId'] == userId):
                    ride = rides.insert_one({'driverId': current_user.id, 'riderId': userId, 'textAddress': rideRequest['textAddress'], 'address': rideRequest['address'], 'pickup': rideRequest['pickup'], 'time': rideRequest['time'], 'chat': []})
                    RideExchangeNamespace.pendingRideRequests[carType].remove(rideRequest)
                    emit('gotride', {'rideId': str(ride.inserted_id)}, room=f"{userId}-WAITING", broadcast=True)
                    emit('redirect', {'url': f"/ride/{str(ride.inserted_id)}"})

    class RequestRide(FlaskForm):
        address = StringField(gettext('Address'), validators=[DataRequired()])
        nowOrLater = RadioField(gettext('Now or Later'), choices=[('now', gettext('Now')), ('later', gettext('Later'))], validators=[DataRequired()])
        time = StringField(gettext('Time'))
        vehicleType = SelectField(gettext('Vehicle Type'), validators=[DataRequired()])
        long = HiddenField(validators=[DataRequired()], render_kw={"id": "long"})
        lat = HiddenField(validators=[DataRequired()], render_kw={"id": "lat"})
        submit = SubmitField(gettext('Request Ride'))

    @app.before_request
    def before_request():
        request.startTime = datetime.now()

    @app.after_request
    def after_request(response):
        end_time = datetime.now()

        if request.startTime is not None:
            app.logger.debug(f"Response Time: {end_time - request.startTime} seconds for [{request.method}] {request.base_url} - {response.status}")

        return response

    # Custom error handler for 404 Not Found
    @app.errorhandler(HttpErrors.NotFound)
    def not_found_error(_): # discard argument because we dont need it
        return render_template("error.html", error=f"{gettext("Page not found")} :("), HttpErrors.NotFound.code

    # Custom error handler for 500 Internal Server Error
    @app.errorhandler(HttpErrors.InternalServerError)
    def internal_server_error(_):
        return render_template("error.html", error=f"{gettext("An internal error occurred")} :("), HttpErrors.InternalServerError.code


    if __name__ == '__main__':
        # need to use app context or else the code immediately crashes whenever i try to access the g object
        with app.app_context():
            # pass values to other blueprints using the g object
            g.mail = mail
            g.login_manager = login_manager
            g.babel = babel
            g.instance_path = app.instance_path
            # you need to import them here in order to avoid circular imports
            from auth import auth_blueprint
            app.register_blueprint(auth_blueprint)
            from profiles import profiles_blueprint
            app.register_blueprint(profiles_blueprint)
        socketio.on_namespace(RideExchangeNamespace('/rideExchange'))
        socketio.on_namespace(RideChatNamespace('/rideChat'))
        socketio.on_namespace(RideNamespace('/ride'))
        socketio.run(app, debug=True)