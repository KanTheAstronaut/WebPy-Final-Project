# User Documentation for Ride Sharing Application

## Table of Contents
1. [Getting Started](#getting-started)
2. [Requesting a Ride](#requesting-a-ride)
3. [Viewing Ride Details](#viewing-ride-details)
4. [Error Handling](#error-handling)

## Getting Started
- **Registration**: Open the application and navigate to the `/auth/signup` path to create a new account. You will need to provide a valid email address and create a password.
- **Login**: After registration, navigate to the `/auth/login` path and log in to the application using your email and password.

## Requesting a Ride
- **Open the Request Ride Page**: After logging in, navigate to the 'Request Ride' page at the `/` path.
- **Enter Ride Details**: The pickup location will be detected based on your real world location, destination address, and desired pickup time. You can also select the type of vehicle you prefer.
- **Submit the Request**: After filling in all the details, submit the request. You will be redirected to a 'Waiting' page at the `/waiting` path while the application finds a driver for you.

## Viewing Ride Details
- **Open the Ride Details Page**: You can view the details of a ride by navigating to the 'Ride Details' page at the `/ride/<ride_id>` path. Replace `<ride_id>` with the ID of the ride.
- **View Ride Details**: On the 'Ride Details' page, you can see the details of the ride, including the driver, the rider, and the pickup and destination addresses.

## Error Handling
- If you enter an invalid address when requesting a ride, you will see a flash message saying "Invalid address!". Please ensure that the address you enter is valid and try again.