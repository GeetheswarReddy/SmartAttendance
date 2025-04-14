from geopy.distance import distance

designated_location = (40.7128, -74.0060) 

user_location = (40.7135, -74.0059)

allowed_distance = 50

dist = distance(designated_location, user_location).meters

print(f"Distance to designated location: {dist:.2f} meters")


if dist <= allowed_distance:
    print("Attendance Verified: User is within the allowed range.")
else:
    print("Attendance Denied: User is not within the allowed range.")

import geocoder

# Get location based on your IP address
g = geocoder.ip('me')
print("Your current coordinates are:", g.latlng)


 