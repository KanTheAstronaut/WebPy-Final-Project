# Technical Documentation for Ride Sharing Application

## Table of Contents
1. [Application Structure](#application-structure)
2. [Requesting a Ride](#requesting-a-ride)
3. [Viewing Ride Details](#viewing-ride-details)
4. [Error Handling](#error-handling)

## Technical
The admin panel pasword is `HatsuneMiku`.

## Application Structure
The application is structured as a Flask web application. The main routes include:
- `/`: The home page where users can request a ride.
- `/waiting`: The page users are redirected to after requesting a ride.
- `/ride/<ride_id>`: The page where users can view the details of a specific ride.

## Requesting a Ride
- **Route**: `@app.route('/', methods=['GET', 'POST'])`
- **Form**: `RequestRideForm`
- **Template**: `request_ride.html`
- **Functionality**: This route handles the form submission for ride requests. If the form is valid, it creates a new ride request and redirects the user to the `/waiting` page.

## Viewing Ride Details
- **Route**: `@app.route('/ride/<ride_id>', methods=['GET'])`
- **Template**: `ride_details.html`
- **Functionality**: This route displays the details of a specific ride. The `ride_id` in the URL is used to fetch the ride details from the database.

## Error Handling
- **Functionality**: If a user enters an invalid address when requesting a ride, a flash message is displayed. This is handled in the `/` route by checking the validity of the address before creating the ride request.