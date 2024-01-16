class Direction:
    AWAY = "away"
    AWAY_DOWN = "away_down"
    AWAY_DOWN_LEFT = "away_down_left"
    AWAY_DOWN_RIGHT = "away_down_right"
    AWAY_LEFT = "away_left"
    AWAY_LEFT_UP = "away_left_up"
    AWAY_LEFT_UP = "away_left_up"
    AWAY_RIGHT = "away_right"
    AWAY_RIGHT_UP = "away_right_up"
    AWAY_UP = "away_up"
    DOWN = "down"
    DOWN_LEFT = "down_left"
    DOWN_LEFT_TOWARDS = "down_left_towards"
    DOWN_RIGHT = "down_right"
    DOWN_RIGHT_TOWARDS = "down_right_towards"
    DOWN_TOWARDS = "down_towards"
    LEFT = "left"
    LEFT_TOWARDS = "left_towards"
    LEFT_TOWARDS_UP = "left_towards_up"
    LEFT_UP = "left_up"
    RIGHT = "right"
    RIGHT_TOWARDS = "right_towards"
    RIGHT_TOWARDS_UP = "right_towards_up"
    RIGHT_UP = "right_up"
    TOWARDS = "towards"
    TOWARDS_UP = "towards_up"
    UP = "up"
    UNKNOWN = "unknown"


# Positive and negative Earth gravity
DEFAULT_TOLERANCE = 9.68 * (2 / 6)


class BNO055_Tilt_Direction:
    @staticmethod
    def from_acceleration(
        x: float, y: float, z: float, tolerance: float = None
    ) -> Direction:
        tolerance = tolerance or DEFAULT_TOLERANCE

        if tolerance <= x:
            if tolerance <= y:
                if tolerance <= z:
                    return Direction.LEFT_TOWARDS_UP
                elif -tolerance < z < tolerance:
                    return Direction.LEFT_TOWARDS
                elif z <= -tolerance:
                    return Direction.DOWN_LEFT_TOWARDS
            elif -tolerance < y < tolerance:
                if tolerance <= z:
                    return Direction.LEFT_UP
                elif -tolerance < z < tolerance:
                    return Direction.LEFT
                elif z <= -tolerance:
                    return Direction.DOWN_LEFT
            elif y <= -tolerance:
                if tolerance <= z:
                    return Direction.AWAY_LEFT_UP
                elif -tolerance < z < tolerance:
                    return Direction.AWAY_LEFT
                elif z <= -tolerance:
                    return Direction.AWAY_DOWN_LEFT
        elif -tolerance < x < tolerance:
            if tolerance <= y:
                if tolerance <= z:
                    return Direction.TOWARDS_UP
                elif -tolerance < z < tolerance:
                    return Direction.TOWARDS
                elif z <= -tolerance:
                    return Direction.DOWN_TOWARDS
            elif -tolerance < y < tolerance:
                if tolerance <= z:
                    return Direction.UP
                elif -tolerance < z < tolerance:
                    return Direction.UNKNOWN
                elif z <= -tolerance:
                    return Direction.DOWN
            elif y <= -tolerance:
                if tolerance <= z:
                    return Direction.AWAY_UP
                elif -tolerance < z < tolerance:
                    return Direction.AWAY
                elif z <= -tolerance:
                    return Direction.AWAY_DOWN
        elif x <= -tolerance:
            if tolerance <= y:
                if tolerance <= z:
                    return Direction.RIGHT_TOWARDS_UP
                elif -tolerance < z < tolerance:
                    return Direction.RIGHT_TOWARDS
                elif z <= -tolerance:
                    return Direction.DOWN_RIGHT_TOWARDS
            elif -tolerance < y < tolerance:
                if tolerance <= z:
                    return Direction.RIGHT_UP
                elif -tolerance < z < tolerance:
                    return Direction.RIGHT
                elif z <= -tolerance:
                    return Direction.DOWN_RIGHT
            elif y <= -tolerance:
                if tolerance <= z:
                    return Direction.AWAY_RIGHT_UP
                elif -tolerance < z < tolerance:
                    return Direction.AWAY_RIGHT
                elif z <= -tolerance:
                    return Direction.AWAY_DOWN_RIGHT

        return Direction.UNKNOWN
