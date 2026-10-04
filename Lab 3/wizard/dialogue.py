"""Prepared lines for the One More Thing Bag.

Every line is phrased as a question or a reminder. The bag cannot see inside
itself and cannot verify that anything is packed, so no line may claim that it
can ("I see your laptop", "your charger is packed"). If a participant asks the
bag to check, the wizard uses `cant_see`.

`listen` controls what happens after the line is spoken:
    True  -> go straight to LISTENING for the participant's answer
    False -> go back to READY (the conversation is over, or we are waiting)
"""

OPENING_ID = "opening"

LINES = [
    # --- opening / turn repair ---
    {"id": "opening", "group": "Start",
     "text": "Hi! Before you head out, where are you going today?", "listen": True},
    {"id": "clarify", "group": "Repair",
     "text": "Sorry, I didn't quite catch that. Could you say it again, a little slower?",
     "listen": True},
    {"id": "no_speech", "group": "Repair",
     "text": "I didn't hear anything. Where are you headed today?", "listen": True},
    {"id": "cant_see", "group": "Repair",
     "text": "I can't see inside the bag, so take a quick look to make sure.", "listen": True},

    # --- class / presentation ---
    {"id": "class_laptop", "group": "Class",
     "text": "Are you presenting from your own laptop, or the classroom computer?",
     "listen": True},
    {"id": "class_charger", "group": "Class",
     "text": "Do you have your laptop charger with you?", "listen": True},
    {"id": "class_adapter", "group": "Class",
     "text": "Will you need an adapter to connect to the projector?", "listen": True},
    {"id": "class_id", "group": "Class",
     "text": "Do you need your student ID to get into the building?", "listen": True},

    # --- gym ---
    {"id": "gym_water", "group": "Gym",
     "text": "Do you have a water bottle and a change of clothes?", "listen": True},
    {"id": "gym_lock", "group": "Gym",
     "text": "Will you need a lock for the locker?", "listen": True},

    # --- travel ---
    {"id": "travel_id", "group": "Travel",
     "text": "Do you have your ID or passport on you?", "listen": True},
    {"id": "travel_charger", "group": "Travel",
     "text": "Is your phone charger with you for the trip?", "listen": True},

    # --- work / errands ---
    {"id": "work_badge", "group": "Work & errands",
     "text": "Do you need your work badge or building key?", "listen": True},
    {"id": "errand_bags", "group": "Work & errands",
     "text": "Do you want to bring a reusable bag for the shopping?", "listen": True},

    # --- general ---
    {"id": "general_basics", "group": "General",
     "text": "Quick check: do you have your keys, phone, and wallet?", "listen": True},
    {"id": "general_umbrella", "group": "General",
     "text": "Would an umbrella or a jacket be useful today?", "listen": True},
    {"id": "general_usual", "group": "General",
     "text": "Is there anything you usually forget for this?", "listen": True},

    # --- wrapping up ---
    {"id": "wait", "group": "Wrap up",
     "text": "No problem, go grab it. I'll be here.", "listen": False},
    {"id": "next_time", "group": "Wrap up",
     "text": "Is there anything you want me to ask about next time?", "listen": True},
    {"id": "noted", "group": "Wrap up",
     "text": "Okay, I'll ask about that next time.", "listen": False},
    {"id": "goodbye", "group": "Wrap up",
     "text": "Sounds like you're set. Have a great day!", "listen": False},
]

BY_ID = {line["id"]: line for line in LINES}
