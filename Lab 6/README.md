# Distributed Interaction

**NAMES OF COLLABORATORS HERE**  Wenqing Pan(wp273 ); Mandy Mao(mm3599)；Sirapop Umnakkittikul(su97); Feiyu Zhou(fz283)



---

## Part A: MQTT Messaging


**💡 Brainstorm 5 ideas for messaging between devices**

### Idea 1: Collaborative Maze Game

We want to create a multiplayer maze game where three players work together to control a single character and navigate through obstacles to reach the destination.

Each player uses a Raspberry Pi with an APDS-9960 sensor to control a different aspect of the character's movement:

- **Player 1 – Forward/Backward:** Uses hand gestures to control the character's forward and backward movement.
- **Player 2 – Left/Right:** Uses hand gestures to control the character's left and right movement.
- **Player 3 – Speed:** Uses the distance between their hand and the sensor to control the character's speed. Moving the hand closer speeds up the character, while moving it farther away slows it down.

The three Raspberry Pis send their sensor data through MQTT, and the game combines these inputs to control the character in real time.

Players must communicate and coordinate their movements to avoid obstacles and successfully complete the maze. This game explores how people collaborate when control of a single character is distributed across multiple users.

### Idea 2: Collaborative Color Mixing

We want to create an interactive color-mixing system where three players work together to create a new color using their Raspberry Pis and APDS-9960 sensors.

Each player places a colored object near their sensor, and the sensor detects its RGB values. The three Raspberry Pis send their color data through MQTT to a shared screen.

The screen displays the three players' individual colors and a fourth color created by mixing all three colors together.

As players change the colors in front of their sensors, the mixed color updates in real time.

This interaction allows players to experiment with different color combinations and explore how individual inputs can contribute to a shared visual result.

### Idea 3: Collaborative Virtual Pet

We want to create a virtual pet that three players can take care of together using their Raspberry Pis and sensors.

Each player is responsible for a different activity:

- **Player 1 – Feeding:** Uses different colors to select food for the pet.
- **Player 2 – Playing:** Uses hand gestures to play with the pet.
- **Player 3 – Resting:** Uses the proximity sensor to help the pet sleep or wake up.

The three Raspberry Pis send their sensor data through MQTT, and a shared screen displays the pet's current status, including its hunger, happiness, and energy levels.

Players must communicate and work together to keep the pet healthy and happy. This interaction explores how multiple users can share responsibility for a single virtual character.

### Idea 4: Digital Campfire

We want to create a virtual campfire that responds to the presence and participation of three people.

Each Raspberry Pi uses its proximity sensor to detect whether a player's hand is near the sensor. The devices send their proximity values through MQTT to a shared display.

The campfire changes based on how many players are participating:

- **One player:** A small flame appears.
- **Two players:** The fire becomes brighter and larger.
- **Three players:** The campfire reaches its maximum size.
- **No players:** The fire gradually fades away.

This interaction explores how physical presence can be represented digitally and how multiple people can contribute to a shared experience, even when they are in different locations.

### Idea 5: Collaborative Cooking Game

We want to create a cooking game where three players work together to prepare a virtual meal using their Raspberry Pis and sensors.

Each player controls a different part of the cooking process:

- **Player 1 – Ingredients:** Uses the color sensor to select different ingredients.
- **Player 2 – Cooking Actions:** Uses hand gestures to perform actions such as chopping or stirring.
- **Player 3 – Temperature:** Uses the proximity sensor to control the cooking temperature.

The three Raspberry Pis send their sensor inputs through MQTT, and the shared screen shows the cooking process in real time.

Players must coordinate their actions to follow recipes, control the cooking process, and complete dishes successfully. This game explores communication, teamwork, and coordination when different parts of a task are controlled by different people.

---

## Part B: Collaborative Pixel Grid


**📸 Include: Screenshot of grid + photo of your Pi setup**

### Pixel Grid Screenshot

![Collaborative Pixel Grid](pixel_grid.jpg)

### Raspberry Pi Setup

![Raspberry Pi with APDS-9960 Sensor](pi_setup.jpg)

---

## Part C: Make Your Own

### Deliverables


**1. Project Description**

Our project is an interactive color-mixing system where three players work together to create a shared color using Raspberry Pis and APDS-9960 color sensors.

Each player uses a Raspberry Pi connected to a color sensor. By placing different colored objects near the sensor, players can control their individual colors. The three Raspberry Pis send their RGB values through MQTT to a shared screen, which displays all three individual colors alongside a fourth color created by combining them. As players change their objects, the mixed color updates in real time.

What makes this project interesting is that no single player has full control over the final color. Instead, the result depends on everyone's input, encouraging players to communicate, experiment, and collaborate. Players can try different color combinations, observe how their individual choices affect the shared result, and work together to create a specific color.

Through this interaction, we hope to create a simple and playful experience that demonstrates how multiple physical devices can communicate and contribute to a shared digital outcome.



**2. Architecture Diagram**

**Demo Video:** [Watch our project demo](https://drive.google.com/file/d/1tm64V-Qqm8RqUIZHdSv-qdsiuE-q7WkZ/view?usp=sharing)


![Architecture Diagram](AD.png)

Our system consists of three Raspberry Pis, each connected to an APDS-9960 color sensor, an MQTT broker, and a shared display.

- **Input:** Each player places a colored object near their APDS-9960 sensor. The sensor detects the object's RGB values, which are read by the connected Raspberry Pi.

- **Communication:** Each Raspberry Pi publishes its RGB data to a separate MQTT topic through Wi-Fi. The MQTT broker receives these messages and forwards them to the application subscribed to the three topics.

- **Computation:** A Python application receives the RGB values from all three Raspberry Pis and calculates a mixed color by combining their RGB components.

- **Output:** The shared screen displays four color blocks: one for each player's detected color and a fourth showing the mixed color. Whenever a player changes their colored object, the system receives updated sensor data and recalculates the mixed color, allowing everyone to see the result in real time.


**3. Build Documentation**

#### Photos of each Pi + sensors

![Pi Photo](3.1.png)

We used three Raspberry Pis as players:

- **Player 1:** `morinz`
- **Player 2:** `raspberrypiWenqingPi`
- **Player 3:** `raspberrypimaoman`

Each Pi has an APDS-9960 color sensor connected with a Qwiic cable. The shared screen is a web page that runs on a laptop.

#### MQTT Topics Used

All three Pis publish to the class broker at `farlab.infosci.cornell.edu` on port `1883`.

Each player has its own topic:

- `IDD/morinmig/colormix/player1`
- `IDD/morinmig/colormix/player2`
- `IDD/morinmig/colormix/player3`

Each Pi sends about 10 messages a second. Every message is a small JSON object with the player number, the color, whether something is held over the sensor, the proximity reading, and the time it was sent. For example:

![Pi Photo](3.2.png)

The shared screen listens to all three at once with the wildcard topic IDD/morinmig/colormix/+ 

#### Code Snippets with Explanations

The project has two files. color_mix_pi.py runs on each player's Pi, and color_mix_display.py runs the shared screen. We wrote the code with help from Claude, an AI assistant.

On each Pi (use 2 and 3 on the other Pis):

![Pi Photo](3.3.png)

On the laptop, then open http://localhost:8091 in a browser:

![Pi Photo](3.4.png)

Reading the sensor. Each Pi reads the color and how close something is. A player only counts as holding a color when the proximity is 40 or more. With nothing in front, the sensor still picks up a pinkish color from the room light, so without this check every player would always be counted.

![Pi Photo](3.5.png)

Cleaning up the color. The sensor reads blue too weakly, so we boost it, then scale the color so the strongest channel is 255. This keeps the hue but not the brightness. We also blend each new reading with the last one so the screen does not flicker.

![Pi Photo](3.6.png)

Publishing. Each Pi sends its color to its own topic 10 times a second.

![Pi Photo](3.7.png)

Receiving. The shared screen subscribes to all three topics with one wildcard. It saves the latest message from each player and when it arrives.

![Pi Photo](3.8.png)

Mixing. A player is offline if nothing has arrived from them for 3 seconds. The mixed color is the average of the players who are holding something up, like shining three colored lights on the same spot.

![Pi Photo](3.9.png)

Showing it. The web page asks for the latest colors about 7 times a second and paints the four circles.

![Pi Photo](4.10.png)

Full codes are in color_mix_display.py and color_mix_pi.py


**4. User Testing**
- **Test with 2+ people NOT on your team**

#### Photos / Videos of Use

- **User 1:** [Watch User 1 Testing Video](https://drive.google.com/file/d/1nBu1ppzmCI5OW9RHNpTrqVllPFEvTGXg/view?usp=sharing)
- **User 2:** [Watch User 2 Testing Video](https://drive.google.com/file/d/15iNTaVnxwqNeeKmJr9hhpLn_QMIm9Wpz/view?usp=sharing)

#### What Did They Think Before Trying?

Before trying it, both testers expected the screen to show only the color of the object they were holding, like a simple color detector. One of them thought they had to touch or tap the sensor to make it work, so we had to explain that holding the object close was enough.

#### What Surprised Them?

The biggest surprise was that the mixed color changed when they moved their object, even though they were still using the same object. This made them realize that the relative position between the object and the sensor could affect the detected color.

They were also surprised that their color disappeared from the mix as soon as they pulled their object away, which made them feel that their actions directly influenced the shared result.

#### What Would They Change?

Both testers wanted a goal, like a target color the team has to match, because they weren't sure what they were supposed to make.

One suggested making the colors mix like paint, since that's how most people think about mixing colors.

They also suggested showing which object each player is holding, or showing each player's color on their own Pi's screen, so they wouldn't have to keep looking up at the shared screen.


**5. Reflection**

#### What Worked Well?

MQTT made it simple. Each Pi publishes to its own topic, and the screen picks up all three with one wildcard, so it never needs the Pis' IP addresses.

The mix updates fast enough to feel live, and the "offline" and "hold a color up" labels show who is missing.

A demo mode that sends made-up colors also let us test the screen before all three Pis were ready.

#### Challenges with Distributed Interaction?

Most problems were hardware and network, not code.

One sensor did not show up until we reconnected it, the Pis' IP addresses kept changing, and the screen could not be opened from another laptop when it ran on a Pi, so we moved it to a laptop.

Player 1's sensor also read about 20 with nothing held up, so we raised the threshold from 5 to 40.

Each Pi belongs to a different teammate, so we also had to get SSH access to every one before we could set it up.

#### How Did Sensor Events Work?

Each Pi checks its sensor 10 times a second and always sends its color.

Proximity decides whether a player is holding something up, and the screen marks a player offline after 3 seconds with no messages.

Sending all the time is simple and fixes itself if a message gets lost, but most messages repeat the same color.

#### What Would You Improve?

We would add a target color for the team to match, offer paint-style mixing (averaging turns yellow and blue into gray, not green), calibrate each sensor automatically, and start the scripts when the Pis boot.

We would also show each player's color on their own Pi's screen, so they do not have to keep looking up at the shared screen.

#### Where Did Computation Happen in Your System, and Why There?

*(If you used a language model: did it run on every event, or only at setup?)*

Each Pi reads and cleans up its own color, so it sends small, ready-to-use messages.

The laptop does the mixing because it is the only place with all three colors.

We did not use a language model, since the mix is simple math.

The browser only draws the circles, asking the laptop for the latest colors about 7 times a second.

---



Resources: [MQTT Guide](https://www.hivemq.com/mqtt-essentials/) | [Paho Python](https://www.eclipse.org/paho/index.php?page=clients/python/docs/index.php) | [Flask-SocketIO](https://flask-socketio.readthedocs.io/)
