# Observant Systems: Overnight Sensation

**Team:**

**Members:** Full Name (netid, github-handle), ...

Feiyu Zhou (fz283)
Sirapop Umnakkittikul (su97)

**Project name:** Desk Watch

<details>
	<summary><strong>Instructions for Students (Click to Expand)</strong></summary>
  
	**Submission Cleanup Reminder:**
	- This README.md contains extra instructional text for guidance.
	- Before submitting, remove all instructional text and example prompts from this file.
	- You may delete these sections or use the toggle/hide feature in VS Code to collapse them for a cleaner look.
	- Your final submission should be neat, focused on your own work, and easy to read for grading.
  
	This helps ensure your README.md is clear, professional, and uniquely yours!
</details>


For lab this week, we focus on creating interactive systems that can detect and respond to events or stimuli in the environment of the Pi, like the Boat Detector we mentioned in lecture. 
Your **observant device** could, for example, count items, find objects, recognize an event or continuously monitor a room.

This lab will help you think through the design of observant systems, particularly corner cases that the algorithms need to be aware of.

**New this year: the AI runs on the Pi.** Your Pi 5 can run an object detector ([YOLO](https://docs.ultralytics.com/)) and a small language model ([Qwen](https://ollama.com/library/qwen3.5) through [Ollama](https://ollama.com)) completely offline. In Part 1 you get both running and connect them: YOLO *sees*, Qwen *reasons* about what was seen. These models are slow, but they have all night. In Part 2 you use them to design a **night-time interaction**: what you tell the device before bed, what it does while you sleep, and what it shows you when you wake up.

**Please indicate anyone that helped with this Lab here.**
Be generous in acknowledging their contributions! And also recognizing any other influences (e.g. from YouTube, Github, Twitter) that informed your design.

Part 2 draft text was written with help from Cursor. We still need to change it after real feedback, the night run, and our own edits. 

## Overview

**Part 1: the tools**

A) [Set up your Pi for on-device AI](#part-a)

B) [See: recognize people in real time with YOLO](#part-b)

C) [See more: hands and pose with MediaPipe](#part-c)

D) [Reason: run Qwen on the Pi with Ollama](#part-d)

E) [Connect: from YOLO readings to Qwen reasoning](#part-e)

**Part 2: Overnight Sensation**

F) [Read Part 2 and storyboard your night-time interaction](#part-f)

G) [Design the interaction before bed](#part-g)

H) [Incorporate the observant system during sleep](#part-h)

I) [Design the interaction when awake](#part-i)

The tools from earlier versions of this lab (MobileNet, Teachable Machine, Moondream, audio analysis, classic OpenCV) live in the [legacy folder](legacy/README.md). They are optional, but any of them can be the sensor in your Part 2 system.


## Prep for Part 1

Please check the instructions in [prep.md](prep.md) and complete them before lab. The installs in Part A take a while, so prep.md also tells you how to get a head start.

## The Report

This readme.md page in your own repository should be edited to include the work you have done. You can delete everything but the headers and the sections between the \*\*\***stars**\*\*\*. Write the answers to the questions under the starred sentences. Include any material that explains what you did in this lab hub folder, and link it in the readme.

---

# Part 1

## Part A. 
### Set up your Pi for on-device AI

Create a virtual environment and install the requirements. They include `ultralytics` (YOLO), which pulls in torch, so this takes a while:

```
pi@raspberrypi:~$ cd Interactive-Lab-Hub/Lab\ 5
pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python3 -m venv .venv
pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ source .venv/bin/activate
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ pip install -r requirements.txt
```

As in Lab 3, [`uv`](https://docs.astral.sh/uv/) is a much faster drop-in for `pip`: `pip install uv && uv pip install -r requirements.txt`.

### YOLO: download the nano model and export it for the Pi

We use the nano model of [YOLO26](https://docs.ultralytics.com/models/yolo26/), exported once to NCNN, the format that runs fastest on the Pi. This downloads the weights:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python -c "from ultralytics import YOLO; YOLO('yolo26n.pt').export(format='ncnn')"
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ yolo export model=yolo26n.pt format=ncnn
```
If every ultralytics message is followed by a `--- Logging error ---` traceback ending in `UnicodeEncodeError: 'latin-1' codec can't encode character`, fix your shell's locale once::

```
echo 'export LANG=C.UTF-8' >> ~/.bashrc
echo 'export LC_ALL=C.UTF-8' >> ~/.bashrc
echo 'export PYTHONIOENCODING=utf-8' >> ~/.bashrc
source ~/.bashrc
```

The second command converts the .pt model to a .ncnn model.

Test it on an image from the internet. `project="$PWD"` keeps the output in `predict` in the current lab folder; without it, ultralytics writes to a `runs/` folder at the top of your git repo, where you will not think to look.

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ yolo predict model=yolo26n_ncnn_model source=https://ultralytics.com/images/bus.jpg project="$PWD"
```

The result is in `predict/bus.jpg`: boxes around the people and the bus.

Now a photo of your own. Plug in the webcam and take one with `snap.py` (`--delay 3` gives you three seconds to get into the frame), or choose any picture you downloaded from the internet and put under this folder. Put your selected picture after the `source=` Then run the same command on it:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python snap.py --delay 3
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ yolo predict model=yolo26n_ncnn_model source=snap.jpg project=runs
```

Every run gets its own numbered folder, so this one is in `runs/predict2/snap.jpg`; the command prints where it saved. Keep `snap.jpg`, you will show it to Qwen in Part D.

### Ollama: install it and pull Qwen

[Ollama](https://ollama.com) runs language models locally. Nothing leaves the Pi: no API key, no internet after the download.

```
pi@raspberrypi:~ $ curl -fsSL https://ollama.com/install.sh | sh
pi@raspberrypi:~ $ ollama pull qwen3.5:0.8b
pi@raspberrypi:~ $ ollama pull qwen3:0.6b
pi@raspberrypi:~ $ ollama list
```

| model | download | what it does |
|---|---|---|
| `qwen3.5:0.8b` | ~1.3 GB | text **and images**; the one we use in this lab |
| `qwen3:0.6b` | ~0.5 GB | text only, smaller and faster (~16 tokens/s on a Pi 5) |

\*\*\***Include a screenshot of `ollama list` showing your models.**\*\*\*
<img width="831" height="165" alt="image" src="https://github.com/user-attachments/assets/9647f5e5-53a2-4b87-b8de-3d7d020fe72a" />


## Part B. 
### See: recognize people in real time with YOLO

YOLO is an *object detector*: it finds every person, cup, cat and so on (the 80 [COCO](https://cocodataset.org/) classes), draws a box around each, and gives a confidence. For an observant system that is exactly what you want: *how many*, *where*, *how sure*.

Connect your webcam, connect to your Pi through **VNC** (the script opens a window), and run the person detector. Read `yolo_person.py` first; the loop at the bottom is the whole idea.

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py
```

While it runs, walk in and out of the frame, sit down, turn your back, hold up a photo of a person on your phone. Watch the confidence number on the box change with each.

Then press q to quit and run it again with a flag. Each one changes a single thing:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py --conf 0.2     # lower the bar: see what the model is unsure about
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py --conf 0.7     # raise the bar: see what you lose
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py --all          # all 80 classes, not only people: what else is on your desk, and what does it get wrong?
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py --headless     # no window, only the printed readings: how it runs over ssh, and at night
```

\*\*\***Include a short video or screenshots of your experiments with the person detection. Write down three situations where it did not see you, or saw a person who was not there, and what you think the cause was.**\*\*\*
https://drive.google.com/file/d/19KMTYGMlTYd4geVwvQzYywyae3sGzlaQ/view?usp=sharing  
https://drive.google.com/file/d/11gCTF8ug3CqiXqBZVeoKJnOokoHVyeOp/view?usp=sharing  
https://drive.google.com/file/d/1fN1iEMC3c4UQRBo2Ca2w-TZVSluA_dfG/view?usp=sharing
<img width="1179" height="582" alt="image" src="https://github.com/user-attachments/assets/0624192c-c715-4028-b09f-d022ff473a49" />
<img width="1188" height="576" alt="image" src="https://github.com/user-attachments/assets/341ec812-9f40-42bc-9722-1639724ab07d" />

Sometimes the detector drew a person box on the wall when nobody was there, probably because shadows, uneven lighting and edges like a door frame made shapes that looked like a body outline. It also detected a cardboard box as a person, since the box is roughly the size of an upper body and its brown color is close to skin tones and clothing in low light. Additionally, it detected my backpack sometimes as a person. All 3 happened because YOLO does not actually understand what a person is and only matches patterns of shapes, edges and colors it learned from photos. It still detected me when I turned my back, so it relies on body shape more than on seeing a face. Raising the confidence threshold removes some of the false boxes, but it also makes the detector miss real people more often.

## Part C. 
### See more: hands and pose with MediaPipe

YOLO tells you that a person is there. Google's [MediaPipe](https://mediapipe.dev/) tells you what their hands and body are doing: face, hand and body pose detection, fast on the Pi.

![Media pipe](Readme_files/mp.gif)

The demo plays a looping audio file, so make the helper script executable first:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ chmod +x loop_audio.sh
```

Connect your webcam, connect to your Pi through **VNC**, and run the hand pose script:
(***it will not work if you use ssh from your laptop***)

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python hand_pose.py
```

Try the two main features of this script: 1) pinching for percentage control (the thumb-to-index distance sets the volume), and 2) "[Quiet Coyote](https://www.youtube.com/watch?v=qsKlNVpY7zg)" for instant percentage setting (the gesture mutes it). Notice how this example uses hardcoded positions and relates those positions with a desired set of events, in `hand_pose.py`: a hand is 21 landmark coordinates, and an *event* is a rule you write over them. That is the same job as `interpret()` in Part E.

Consider how you might use this position based approach to create an interaction, and write how you might use it on either face, hand or body pose tracking.

\*\*\***Include a screenshot or short video of the hand pose demo, and write how you might use face, hand or body pose tracking in your observant system.**\*\*\*
https://drive.google.com/file/d/1k_O0kMp0HoOpa-b1eOVRvFzQyKQat0a6/view?usp=sharing  

Video: https://drive.google.com/file/d/1e2plWWazIMQ6d1eZEN4pTs2vr1Cy_PXA/view?usp=sharing

The hand pose demo works by tracking 21 points on the hand and turning their positions into events, like measuring the distance between the thumb and index finger to set the volume. I would use the same approach to control the light level in the room. Widening or closing a pinch would make the lights brighter or dimmer, and a Quiet Coyote gesture would turn them off completely. This fits a night-time system because you could dim the lights from bed as you wind down, without getting up or looking for a switch. The rules are simple to write since they only compare a few landmark positions, but the device would need to ignore hands that are just moving around so the lights don't change by accident.

## Part D. 
### Reason: run Qwen on the Pi with Ollama

Talk to the model in the terminal first. Qwen3 models "think" before they answer, which is slow on a Pi, so turn it off. Then ask about something you can check:

```
pi@raspberrypi:~ $ ollama run qwen3.5:0.8b
>>> /set nothink
>>> Tell me a bit about the history of Roosevelt Island. Three sentences.
>>> /bye
```

Roosevelt Island is a good first question because you know the ground truth: it was Blackwell's Island, then Welfare Island, got its current name in 1973, and Cornell Tech opened on it in 2017. Count how many of the model's facts are true.

From Python, qwen requests can be triggered by the `ask_qwen.py` script. It turns thinking off, tells the model to answer in at most three sentences, and cuts it off after 120 tokens (`--max-tokens` changes that), because a small model left alone writes an essay. Read the script, then run:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python ask_qwen.py "Tell me a bit about the history of Roosevelt Island."
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python ask_qwen.py --model qwen3:0.6b "Tell me a bit about the history of Roosevelt Island."
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python ask_qwen.py --image snap.jpg "What is in this photo?"
```

Things in the [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md) worth knowing:

* `think: false` skips the reasoning trace. Always, on a Pi. `ask_qwen.py` sends it on every request; `--think` turns the trace back on for one question, so you can see what you are skipping and how long it takes.
* `format` makes the model answer as JSON with the fields you name (`--json`). Handy when a display or a servo has to read the answer.
* `images` sends a photo along with the prompt (`--image snap.jpg`, the photo from Part A). `qwen3.5:0.8b` can look at pictures.

A 0.8B model is slow and sometimes wrong. It will invent events that are not in the data and agree with a wrong premise. Give it the data, keep its job narrow, and decide what the device does when the model is unsure.

\*\*\***Ask Qwen three questions to answer. Paste the questions, the answers and how long each took. Try one of them with `qwen3:0.6b` and compare.**\*\*\*
<img width="1716" height="642" alt="406e14515c216829bb5562bc1e6f6d6d" src="https://github.com/user-attachments/assets/d08cb537-bebc-490d-978e-b2601cd78b52" />

I asked both models who the Prime Minister of Thailand is. qwen3.5:0.8b took 25.6 seconds and said Yingluck Shinawatra has served since 2017 and was re-elected in 2024, which is wrong, because she was Prime Minister from 2011 to 2014. qwen3:0.6b answered in 13.4 seconds, about twice as fast, but only gave a short, misspelled name, Prayong, which seems to mean Prayut Chan-o-cha, who left office in 2023. Both models sounded confident while being wrong, so the smaller model is faster but neither one can be trusted with facts it has to remember, which is why the device should give the model the data instead.

Qwen also said Cornell Tech is an online learning platform, when it is actually a graduate campus on Roosevelt Island.

## Part E. 
### Connect: from YOLO readings to Qwen reasoning

An observant system is a pipeline: a **detector** turns pixels into boxes, an **interpreter** turns boxes into readings in words ("one person, left, close"), the readings pile up in a **log**, and a **reasoner** answers a question about the log. The language model never sees pixels, only the words you chose in the interpreter. That makes the interpreter the most important design decision in the system.

`yolo_to_qwen.py` is the pipeline in one file, one function per stage. Read it before you run it:

* `interpret(r)` is the interpreter. It takes one YOLO result and returns one reading. A person is *left*, *center* or *right* by which third of the frame the middle of their box is in, and *close* if the box is taller than 60% of the frame, *far* otherwise. The reading is a string like `1 person(s) at center/close`, or `nobody`. Fifteen lines, and they decide everything the model can know.
* `watch(seconds)` is the detector and the log. Twice a second it reads a frame, runs YOLO on it and calls `interpret()`. A time-stamped reading goes into the log **only when it differs from the previous one**, so a minute of sitting still is one line, not 120.
* `ask(log, question)` is the reasoner. It pastes the log and your question into one prompt, tells Qwen to answer in at most three sentences using only what is in the log, and sends it to Ollama with thinking off.

Run it through VNC and a window opens with YOLO's boxes, the current reading and the seconds left. Press q to stop watching early. Over plain ssh add `--headless` and you get the same thing minus the window.

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_to_qwen.py
```

It watches for a minute, saves the log to `watch_log.txt` and asks Qwen the default question. The terminal looks something like this:

```
14:02:11 nobody
14:02:19 1 person(s) at right/far
14:02:24 1 person(s) at center/close
14:02:51 nobody

4 lines saved to watch_log.txt
asking Qwen...

Qwen (18.4 s):
One person came in from the right, moved close to the camera, and left after about half a minute. ...
```
https://drive.google.com/file/d/1vTxuZXGkDrBkJOGJ7zRQg8mS8VnjQo5J/view?usp=sharing  
<img width="996" height="882" alt="image" src="https://github.com/user-attachments/assets/ebec9f7b-4702-43d1-bb5f-2ea26714b4ed" />

---

# Lab 5 Part 2: Overnight Sensation

For Part 2, you will use the observant system from Part 1 to design a night-time interaction. On-device AI is slow, so let it work while you sleep. The person meets the device twice: **before bed**, when they hand the night over, and **when awake**, when the device gives something back. In between, the pipeline from Part E runs on its own.

Two flavors, pick one or mix them:

* **Sense all night.** The Pi watches, listens or measures from bedtime until morning and keeps a log.
* **Process all night.** You already have the data (a day of phone photos, a long recording) and the Pi needs hours to get through it.

Two house rules. Sample rather than stream: one look every 5 to 30 seconds is plenty, and it keeps the Pi cool. And keep everything on the Pi: tell the people you live with, point the camera at things rather than at beds, and delete the snapshots after the demo.

## Part F. 
### Read Part 2 and storyboard your night-time interaction

Storyboard a night-time interaction built on your observant system, in three panels:

1. **Before bed.** How does the person hand the night over, and how does the device acknowledge it?
2. **While asleep.** What does the device watch or work through?
3. **When awake.** What is the one thing the person learns, and in what medium?

Stuck? A kitchen that tells you who raided the fridge. A desk that reports whether you actually went to bed. A window that names the quietest hour. A plant that describes its night. Find something better.

Use storyboards and/or [Verplank diagrams](https://ccrma.stanford.edu/courses/250a-fall-2004/IDSketchbok.pdf).

\*\*\***Insert ideas, sketches, Verplank diagrams and storyboards for your night-time interaction here.**\*\*\*

Idea: Desk Watch. The camera sits on the desk. It looks at the desk and the chair. It does not look at the bed. In the morning it tells us one thing. Did anybody come back to the desk.
<img width="1280" height="960" alt="84b5a4617c35d276af78030c99f831bd_720" src="https://github.com/user-attachments/assets/8d3dd4d1-559b-4ad4-8ee5-9389771738f9" />

Panel 1, before bed. I stand at the desk. I do Quiet Coyote at the camera. Same gesture as Part C. The LED dims. A line shows up: "Watching the desk tonight." This sets the morning question. Did anyone come to the desk. It takes about 30 seconds. Then I leave.
<img width="1280" height="960" alt="b8dc77437cd4fbab70e5953dd56f8517_720" src="https://github.com/user-attachments/assets/0cf55ab0-4bed-4d01-9cbb-a89a8330d886" />

Panel 2, while asleep. The Pi looks every 10 seconds. It only cares about people. It writes a new line only when the reading changes. Person, or nobody. If it sees a person, it saves one photo. Every 10 minutes it writes an alive line, so a quiet night is not a crash. Qwen does not run at night. It waits for morning.
<img width="1280" height="960" alt="e4db5819af4879a81b443b1648515101_720" src="https://github.com/user-attachments/assets/a6271164-aeaf-4987-93cc-4902bbba7c43" />

Panel 3, when awake. I run the morning script. If the log is only nobody, the device says "Quiet night. Nobody came to the desk." It does not ask Qwen. If someone was there, Piper reads one short line. The time, and if they were close. One fact. Not a long story.
<img width="1280" height="960" alt="03527975c2bf937324fb98e44199d32c_720" src="https://github.com/user-attachments/assets/1a28e67d-4019-4163-9e0b-7a5f83cd3aa6" />

Verplank, in words. A sketch photo still needs to go here.
The person does Quiet Coyote, then goes to sleep. The device senses with the webcam and YOLO. At night the LED is dim. In the morning the device speaks one sentence.

## Prep for Part 2

1. Look at and give feedback on the Part F storyboards.
   **Put the feedback for your ideas here.**

The idea is clear and I like that it tells you when nothing happened. But the camera can't see well in the dark, so it might miss someone who doesn't turn on a light. It might also be useful to include why you want to know if someone came to the desk. Is it to catch yourself staying up late, or a roommate using your desk?

\*\*\***Post your revised storyboard here.**\*\*\*

This revision comes from our own Part B and Part E tests. We will change it again after classmate feedback.

The camera points at the desk only. In Part B, YOLO drew a person on the wall. It also called a cardboard box a person. So the background has to be plain. No big box. No poster with a person on it. If fake boxes come back, we raise the confidence.

The morning question is only "did a person show up." So `interpret()` does not need left, center, and right. It should say `nobody`, or `person, close`, or `person, far`. Close means the box is tall. Qwen never sees the photo. It only sees these words.

A back view still counts as a person. Part B showed that. That is fine. We are not looking for a face.

We look every 10 seconds. Not a video stream. After the demo we delete the photos in `snaps/`. Roommates have to say yes before the real night.

## Part G. 
### Design the interaction before

The hand-off: the person tells the device what to watch tonight, and the device acknowledges it. Keep it to a thirty-second ritual. A button or a touch (Lab 4), a spoken sentence (Lab 3), a wave or a Quiet Coyote at the camera (Part C). The acknowledgement can be a line on the display, a tone, or an LED that dims rather than lights up. At its simplest, the hand-off just sets the question that the morning will answer.

\*\*\***Describe the interaction before.**\*\*\*

Before bed I walk to the desk. I face the camera. I do Quiet Coyote, the same gesture as Part C. Index finger and pinky stay up. Middle finger and ring finger fold together. The thumb sits near the ring finger. The Pi sees the gesture and starts the night log. The LED goes dim, not bright. The screen says "Watching the desk. Morning question: did anyone come back?" Then I go to bed.

If the room is too dark and the hand pose fails, I press the Lab 4 button once. Same result. The hand-off only sets that one question. I do not have to talk to it. The whole ritual is about 30 seconds.

## Part H. 
### Incorporate the observant system

The Part E pipeline becomes the night shift. `overnight.py` runs your `interpret()` from `yolo_to_qwen.py` every few seconds, people only unless you pass `--all`, and writes the readings to `night_log.jsonl`; the reasoning waits for the morning. Start it inside `tmux` so it keeps running after you close your laptop, and stop it with Ctrl-C in the morning:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ tmux new -s night
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python overnight.py
```

Fake a night first: run it for thirty seconds while you walk around, stop it, and run `morning.py` from Part I. When that looks right, run a real night. If your storyboard needs a sensor rather than the camera, swap in the Lab 4 example code and log its reading the same way.

\*\*\***Screenshots or videos of the running system.**\*\*\*

Screenshot of the fake night, and the real `night_log.jsonl`, go here after we run them on the Pi.

## Part I. 
### Design the interaction after

The reveal. The night produced a log; the morning turns it into something a half-awake person can take in. `morning.py` is the smallest version: it asks Qwen for a three-sentence report.

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python morning.py
```

Make it yours: show the report on the Mini PiTFT, read it aloud with Piper from Lab 3, plot the night as a timeline, or ask for JSON (`--json`, Part D) and move a servo. Whatever you pick, make sure it is honest about a night in which nothing happened.

Morning plan. We keep `morning.py` as the check. Then Piper reads the report out loud, from Lab 3. If nobody was at the desk, it says "Quiet night. Nobody came to the desk." and it does not call Qwen. If someone was there, Qwen gets the log and Piper says one short line. The time, and close or far. Nothing that is not in the log.

## Final documentation

Document all the prototypes and iterations you have designed and worked on. The deliverables for this lab are writings, sketches, photos, and videos that show what your system:

* "Looks like": how the device sits in the room at night, and what it looks like at bedtime and in the morning.
* "Works like": the pipeline from detector to interpreter to log to reasoner, with a real night's data.
* "Acts like": how a person hands the night over and what they get back.

\*\*\***Include a short video of the whole system**\*\*\*
https://drive.google.com/file/d/1A61GbZFxwjUhj2yQwvzyDYzJhsWYdOhK/view?usp=sharing
Looks like. The Pi and the webcam sit on the desk, facing the chair. Not the bed. At bedtime the LED is dim and the screen shows one line. In the morning the same screen shows one sentence, and the speaker says it.

Works like. YOLO looks at a frame. `interpret()` turns the boxes into `nobody` or `person, close` or `person, far`. `overnight.py` writes that to `night_log.jsonl` only when it changes. In the morning `morning.py` reads the log. A quiet night stops there. A night with a person goes to Qwen, and Qwen only gets the words in the log. Real log link goes here after the night run.

Acts like. At night I do Quiet Coyote, or I press the button if the room is dark. The device dims and takes the question. In the morning I get one sentence back. Either nobody came, or someone was there at a certain time.

As always, make sure you document contributions and ideas from others (and AI) explicitly in your writeup.

You are permitted (but not required) to work in groups and share a turn in; you are expected to make equal contribution on any group work you do, and N people's group project should look like N times the work of a single person's lab. Make sure the page for the group turn in is linked to your personal Interactive Lab Hub page.

## Deliverables & Submission for Lab 5

For submission, the readme.md page for this lab should be edited to include the work you have done:
* Upload any materials that explain what you did, including your code and night log, into your Lab 5 repository, and link them in your Lab 5 readme.md.
* Labs are due on Sundays, make sure to submit your Lab 5 readme.md to Canvas.

<details>
  <summary><strong>Submission Cleanup Reminder (Click to Expand)</strong></summary>

  **Before submitting your README.md:**
  - This readme.md file has a lot of extra text for guidance.
  - Remove all instructional text and example prompts from this file.
  - You may either delete these sections or use the toggle/hide feature in VS Code to collapse them for a cleaner look.
  - Your final submission should be neat, focused on your own work, and easy to read for grading.
</details>
