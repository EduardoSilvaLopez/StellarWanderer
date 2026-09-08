from Spaceships.Laser import Laser

class Ship:
    HEIGHT = 10 # meters, up to the camera

    UP_DOWN_SPEED = 1  # meters per second
    RIGHT_LEFT_SPEED = 10  # meters per second
    FORWARD_BACKWARD_SPEED = 10  # meters per second
    ROTATION_SPEED = 10  # degrees per game second

    def __init__(self):
        self.laser = Laser()