import time
import qwiic_proximity
import pi_servo_hat

# Shy Jar
# The lid starts at -30° and closes by turning to 135°, then comes back.
# -30° is about 0.83 ms, just past the usual 1.0 ms end.

SERVO_CH = 0
PWM_HZ = 50
MIN_MS = 1.0
MAX_MS = 2.0
SERVO_SWING = 180
LID_OPEN = -30
LID_CLOSED = 135

MOVE_TIME = 1.0
STEP_DELAY = 0.02

# Higher proximity means the object is closer.
CLOSE_THRESHOLD = 120
OPEN_THRESHOLD = 60
CLOSE_HOLD = 0.3


def pulse_ms(angle):
    return MIN_MS + (angle / SERVO_SWING) * (MAX_MS - MIN_MS)


def move_servo(angle):
    servo.move_servo_position(SERVO_CH, angle, swing=SERVO_SWING)


proximity_sensor = qwiic_proximity.QwiicProximity()
if not proximity_sensor.connected:
    raise RuntimeError(
        "Qwiic proximity sensor not found. Check the Qwiic connection."
    )
proximity_sensor.begin()

servo = pi_servo_hat.PiServoHat(min_pt=MIN_MS, max_pt=MAX_MS)
servo.restart()
servo.set_pwm_frequency(PWM_HZ)
servo.move_servo_position(SERVO_CH, LID_OPEN, swing=SERVO_SWING)

print("Shy Jar ready. Lid is open.")
print(f"{PWM_HZ} Hz, open {pulse_ms(LID_OPEN):.2f} ms, closed {pulse_ms(LID_CLOSED):.2f} ms")
print(f"Close when proximity > {CLOSE_THRESHOLD} for {CLOSE_HOLD}s")
print(f"Open again when proximity < {OPEN_THRESHOLD}")

angle = float(LID_OPEN)
move_from = angle
move_to = angle
move_started = None
lid_shut = False
close_since = None

try:
    while True:
        proximity = proximity_sensor.get_proximity()
        now = time.monotonic()

        if not lid_shut:
            if proximity > CLOSE_THRESHOLD:
                if close_since is None:
                    close_since = now
                elif now - close_since >= CLOSE_HOLD:
                    lid_shut = True
                    print(f"\nHand stayed close ({proximity}). Closing lid.")
            else:
                close_since = None
        elif proximity < OPEN_THRESHOLD:
            lid_shut = False
            close_since = None
            print(f"\nHand left ({proximity}). Opening lid.")

        target = LID_CLOSED if lid_shut else LID_OPEN
        if target != move_to:
            move_from = angle
            move_to = target
            move_started = now
        if move_started is not None:
            elapsed = min(MOVE_TIME, now - move_started)
            angle = move_from + (move_to - move_from) * (elapsed / MOVE_TIME)
            move_servo(angle)
        state = "shut" if lid_shut else "open"
        print(f"Proximity: {proximity:4d}  angle: {angle:6.1f}  {state}", end="\r")
        time.sleep(STEP_DELAY)

except KeyboardInterrupt:
    print("\nStopping. Opening the lid.")
    servo.move_servo_position(SERVO_CH, LID_OPEN, swing=SERVO_SWING)
