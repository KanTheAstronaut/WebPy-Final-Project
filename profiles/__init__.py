from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from flask_babel import gettext
from auth import DriverInformationForm

profiles_blueprint = Blueprint('profiles', __name__,
                        template_folder='templates', url_prefix='/profiles')

@profiles_blueprint.route('/profile')
@login_required
def viewProfile():
    return render_template('profile.html')

@profiles_blueprint.route('/editVehicle', methods=['GET', 'POST'])
@login_required
def editCarInfo():
    if not current_user.driver:
        return redirect('/')
    # update driver information
    form = DriverInformationForm()
    form.carColor.data = current_user.carColor
    form.carLicensePlate.data = current_user.carLicensePlate
    form.carMake.data = current_user.carMake
    form.carModel.data = current_user.carModel
    form.carYear.data = current_user.carYear
    if form.validate_on_submit():
        current_user.carColor = form.carColor.data
        current_user.carLicensePlate = form.carLicensePlate.data
        current_user.carMake = form.carMake.data
        current_user.carModel = form.carModel.data
        current_user.carYear = form.carYear.data
        current_user.UpdateDriver()
        return redirect(url_for('profiles.profile'))
    return render_template('editProfile.html')