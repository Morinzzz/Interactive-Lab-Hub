# Chatterboxes

**NAMES OF COLLABORATORS HERE**

Feiyu (Morin) Zhou and Sirapop Umnakkittikul

[![Watch the video](https://user-images.githubusercontent.com/1128669/135009222-111fe522-e6ba-46ad-b6dc-d1633d21129c.png)](https://www.youtube.com/embed/Q8FWzLMobx0?start=19)

In this lab, we want you to design interaction with a speech-enabled device — something that listens and talks to you. This device can do anything *but* control lights (since we already did that in Lab 1). First, we want you to storyboard what you imagine the conversational interaction to be like. Then you will use wizarding techniques to elicit examples of what people might say, ask, or respond. We then want you to use the examples collected from at least two other people to inform the redesign of the device.

We will focus on **audio** as the main modality for interaction to start; these general techniques can be extended to **video**, **haptics** or other interactive mechanisms in the second part of the Lab.

A note on what you are building with. Speech interfaces are usually taught as two boxes — speech-in, speech-out — and that framing hides the part that actually determines whether an interaction works. Between listening and speaking sits the question of **whose turn it is**: when does the device decide you have finished talking, and how long does it make you wait before it answers? This lab gives you direct control over both, and we will ask you to notice what changes when you move them.

## Prep for Part 1: Get the Latest Content and Pick up Additional Parts

Please check instructions in [prep.md](prep.md) and complete the setup.

### Pick up Web Camera If You Don't Have One

Students who have not already received a web camera will receive their Webcam and at the beginning of lab. If you cannot make it to class this week, please contact the TAs to ensure you get these.

### Get the Latest Content

As always, pull updates from the class Interactive-Lab-Hub to both your Pi and your own GitHub repo.

**\[recommended\]** Option 1: On the Pi, `cd` to your `Interactive-Lab-Hub`, pull the updates from upstream (class lab-hub) and push the updates back to your own GitHub repo. You will need the *personal access token* for this.

```
pi@ixe00:~$ cd Interactive-Lab-Hub
pi@ixe00:~/Interactive-Lab-Hub $ git pull upstream Fall2026
pi@ixe00:~/Interactive-Lab-Hub $ git add .
pi@ixe00:~/Interactive-Lab-Hub $ git commit -m "get lab3 updates"
pi@ixe00:~/Interactive-Lab-Hub $ git push
```

Option 2: On your own GitHub repo, create a pull request to get updates from the class Interactive-Lab-Hub. After you have the latest updates online, go to your Pi, `cd` to your `Interactive-Lab-Hub` and use `git pull`.

---

# Part 1

## Setup

Create and activate a virtual environment for this lab:

```
pi@ixe00:~$ cd Interactive-Lab-Hub/Lab\ 3
pi@ixe00:~/Interactive-Lab-Hub/Lab 3 $ python3 -m venv .venv
pi@ixe00:~/Interactive-Lab-Hub/Lab 3 $ source .venv/bin/activate
(.venv) pi@ixe00:~/Interactive-Lab-Hub/Lab 3 $
```

Install the Python dependencies:

```
(.venv) $ pip install -r requirements.txt
```

This takes a few minutes. If you would like it to take considerably less time, [`uv`](https://docs.astral.sh/uv/) is a drop-in replacement for `pip` that is dramatically faster on the Pi:

```
(.venv) $ pip install uv && uv pip install -r requirements.txt
```

Then run the setup script, which installs the classic speech synthesizers, downloads the voice activity detection model, and pre-fetches a neural voice and a speech recognition model so you are not waiting on downloads during lab:

```
(.venv):~$ cd speech-scripts
(.venv) $ ./setup.sh
```

Check your audio devices before going further. `arecord -l` lists capture devices and `aplay -l` lists playback devices; if your webcam microphone or Bluetooth speaker does not appear, fix that first — every script below assumes the system defaults are the ones you want.

## A. Text to Speech

Your Pi can speak in several quite different ways, and the differences are audible in a way that matters for design. In `speech-scripts/` there are shell scripts for each.

### The classic engines

```
(.venv) $ cd speech-scripts

(.venv) $ sudo apt update
(.venv) $ sudo apt install -y espeak festival festvox-kallpc16k

(.venv) $ ./espeak_demo.sh
(.venv) $ ./festival_demo.sh
```

You can run these `.sh` files by typing `./filename`, and read one with `cat filename`. You can also play audio files directly with `aplay filename` — try `aplay lookdave.wav`.

These are all decades-old technology and they sound like it. `espeak-ng` is a *formant synthesizer*: it generates speech from an acoustic model of the vocal tract, which is why it sounds robotic but also why the whole thing fits in a couple of megabytes and responds instantly. `festival` is *concatenative*: they stitch together recorded fragments of a real speaker, which sounds more human but breaks audibly at the seams.

### Neural TTS with Piper

Note that the Piper command line changed in version 1.x — voices are now downloaded explicitly with `python3 -m piper.download_voices`, and you invoke it as `python3 -m piper`. Tutorials you find online may show the old `echo ... | piper --model ...` form, which no longer works. Browse the [voice samples](https://rhasspy.github.io/piper-samples) and download a different one if you'd like:

```
(.venv) $ python3 -m piper.download_voices en_US-lessac-medium
```

[Piper](https://github.com/OHF-Voice/piper1-gpl) synthesizes speech with a small neural network, runs comfortably on the Pi 5, and sounds markedly better than the above.

```
(.venv) $ ./piper_demo.sh
```

The demo script also shows `--output-raw`, which streams audio to the speaker as it is generated rather than writing a file first. Listen for the difference in how quickly speech begins. In a conversational system this gap is the thing your user experiences as responsiveness.

\*\***Write your own shell file to use your favorite of these TTS engines to have your Pi greet you by name.**\*\*
(This shell file should be saved to your own repo for this lab.)

Script: [`speech-scripts/greet_morin_mig.sh`](speech-scripts/greet_morin_mig.sh). I used Piper (`en_US-lessac-medium`) with `--output-raw`, so playback starts while the rest of the sentence is still being synthesized.

```bash
(.venv) $ ./greet_morin_mig.sh
```

\*\***Then answer: Is the same greeting, in these different voices, the same greeting? Describe one concrete way the voice changed what the utterance seemed to mean or who seemed to be speaking.**\*\*

No. The words can be identical and the greeting still is not the same, because the voice tells you who is speaking and what kind of relationship they are claiming.

Concrete example: I said “Hi Morin and Mig. Welcome back.” with all three engines.

- **espeak** (`-ven+f2`) made it sound like a toy or an old GPS. The “welcome back” did not feel warm; it felt like a status message a machine is required to play.
- **festival** made the same line feel more like a person, but a slightly stiff, older male one. Because we had just heard it say the HAL line about Dave, the greeting picked up some of that “I am watching you” tone even though the words were friendly.
- **Piper / lessac** sounded like a calm American narrator. “Welcome back” suddenly meant *I know you, you have been here before*, closer to a host than a beep.

So the utterance’s meaning moved with the voice: system prompt vs. slightly ominous attendant vs. someone greeting you at the door. That is why we picked Piper for the greeting script — not only because it sounds better, but because it is the only one that actually felt like a greeting.

## B. Speech to Text

We use [faster-whisper](https://github.com/SYSTRAN/faster-whisper), a reimplementation of OpenAI's Whisper model that runs several times faster on CPU and does not require PyTorch. All processing happens on the Pi; nothing is sent to a server.

```
(.venv) $ python transcribe.py lookdave.wav
```

The transcript is not the interesting output here — the timings are. Run it again with a larger model and compare:

```
(.venv) $ python transcribe.py lookdave.wav --model base.en
(.venv) $ python transcribe.py lookdave.wav --model small.en
#  noted that the first run may take longer because the model is downloaded, and that the HF unauthenticated-request warning is expected and not an error.
```

Available sizes, smallest first: `tiny.en`, `base.en`, `small.en`, `medium.en`. The `.en` variants are English-only and faster than their multilingual counterparts at the same size.

\*\***Record a few seconds of your own speech (`arecord -d 5 -f cd -c 1 -r 16000 test.wav`) and transcribe it with at least two model sizes. Report the real-time factor for each. At what point does the accuracy improvement stop being worth the delay, for a system that has to answer you?**\*\*

Recording: `speech-scripts/test.wav` (5 seconds of my own speech).

| Model | Transcript | Audio duration | Transcription time | Real-time factor |
| --- | --- | --- | --- | --- |
| `tiny.en` | Hi, this is Morin, I'm an interactive | 5.00s | 1.03s | **0.21x** |
| `base.en` | Hi, this is Morin. I'm in interactive. | 5.00s | 1.94s | **0.39x** |

Both are faster than real time (`tiny.en` transcribed 5s of audio in 1.03s; `base.en` took 1.94s). Model load is a one-time cost per process (`tiny.en` 0.55s, `base.en` 14.92s on first download). After that, only transcription time matters.

For a system that has to answer you, the accuracy improvement already stopped being worth it at `base.en`. It was almost **2× slower**, and it did not even fix the sentence: `tiny.en` heard “I'm **an** interactive,” `base.en` heard “I'm **in** interactive.” I would ship `tiny.en`, keep the model resident (as `listen.py` does), and design around leftover errors with a confirmation turn instead of waiting on a bigger model. `small.en` / `medium.en` would only add more delay.

\*\***Write your own script that verbally asks for a numerical input (a phone number, zipcode, number of pets) and records the answer the respondent provides.**\*\* Numbers are a good stress test — transcription systems make characteristic errors on digit strings, and you will want to know what they are before you design around them.

Script: [`speech-scripts/ask_number.py`](speech-scripts/ask_number.py)

It uses Piper to ask for a five-digit zip code (you can make one up), records 6 seconds from the webcam mic, saves `zipcode_answer.wav`, and transcribes with faster-whisper.

```bash
(.venv) $ python ask_number.py
(.venv) $ python ask_number.py --model base.en
```

What I am listening for in the transcript: `oh` vs `zero`, missing digits, commas (`10,011` instead of `10011`), or the zip written as words (`nine four one oh three`). Those errors are why a later dialogue should confirm numbers instead of trusting the first transcript.

## C. Turn-taking: knowing when someone has stopped talking

Everything so far has worked on fixed audio files. A real conversational device does not get told when to start and stop recording — it has to decide. This is the problem that makes speech interfaces hard, and it is mostly not a speech recognition problem.

We use a **voice activity detector** (VAD) to segment the microphone stream into utterances. `listen.py` runs Silero VAD continuously and hands each detected utterance to faster-whisper:

```
(.venv) $ cd speech-scripts
(.venv) $ python listen.py
```

Speak, pause, and watch it transcribe. Now change the endpointing threshold — the amount of silence the system requires before it decides your turn is over:

```
(.venv) $ python listen.py --min-silence 0.2
(.venv) $ python listen.py --min-silence 1.5
```

\*\***Try both extremes, and something in between. Describe what each one feels like to talk to. Note specifically: at 0.2s, what kinds of normal speech get cut off? At 1.5s, what does the delay make the system seem like?**\*\*

Same intended line each time: *I want a latte, um, actually a cappuccino.* `--min-silence` is turn-taking, not recognition.

**0.2s** — `[4.9s speech, 1.00s to transcribe] I want to say actually a cup of china`

It grabbed the turn the instant I stopped. I did not leave a long enough hole in the middle for it to split the sentence, so it did not cut me into two transcripts — it cut *inside* the words instead. The “um” / “latte” hesitation got eaten, and “cappuccino” became “cup of china.” At 0.2s, the speech that gets cut off is the small stuff in a repair: the filled pause, the word you are about to take back, the switch from first order to second. It feels jumpy, like someone finishing your sentence.

**0.4s (default)** — `[4.6s speech, 0.99s to transcribe] I want to take actually a cup of china`

Almost the same clip length and almost the same wait. It still feels like a short-order window: fine if the line is already in your mouth, still messy if you change your mind mid-sentence. “say” became “take.” This is the usable in-between for a command, not for thinking out loud.

**1.5s** — `[13.8s speech, 1.37s to transcribe] I don't want to let's hear it. Actually, I'll come with Cheena. What time is it?`

This is the one that changed how it *felt*. After I finished, nothing happened, so I kept going and even threw in a second question. The system treated all of that as one turn (13.8s of speech). The delay makes it seem like it did not hear me, or like a laggy phone call — vacant, a little deaf. The failure mode is not cutting you off; it is swallowing the next thing you say while you wait.

No correct value. A drink order wants ~0.4s so it can move after a short pause. Something that lets you think out loud needs closer to a second, or it will either clip the “actually…” or vacuum up “what time is it?” into the same utterance.

### The complete loop

`echo_bot.py` puts the pieces together: it listens, endpoints, transcribes, and speaks a reply through Piper. The dialogue policy is deliberately trivial — it repeats what you said — so that everything you notice is a property of the timing rather than the content.

```
(.venv) $ python echo_bot.py
```

Default 0.4s endpointing. It heard `I want to cover the tape` (still the cappuccino line, even more mangled) and said `You said: I want to cover the tape.` Timing: **asr 1.01s | tts first audio 0.28s | total gap 1.29s**. Piper itself was quick; the dead air was almost all Whisper. Even with a “fast” endpoint, you still wait more than a second before the device talks back — and that gap is what feels like the system thinking.

## D. Storyboard

Storyboard and/or use a Verplank diagram to design a speech-enabled device. (Stuck? Make a device that talks for dogs. If that is too stupid, find an application that is better than that.)

\*\***Post your storyboard and diagram here.**\*\*

<img width="1699" height="906" alt="image" src="https://github.com/user-attachments/assets/f9f3ad08-f3bf-48f5-8dc1-8bb0bd1049b1" />

Write out what you imagine the dialogue to be. Use cards, post-its, or whatever method helps you develop alternatives or group responses.

Concept: DoorBuddy. DoorBuddy is a speech device by the front door. When you approach with a bag, it asks where you're going and follows up with a targeted question to catch anything you forgot. Afterward, it asks if there's anything new to remember next time.

Storyboard: The user heads for the door with a bag. DoorBuddy asks, "Where are we going?" The user says they're presenting in class. DoorBuddy asks whether they're using their laptop or the class desktop. The user freezes, realizes the laptop isn't in the bag, and runs back for it. When they return, DoorBuddy asks if there's anything else to remember for next time

\*\***Please describe and document your process.**\*\*

Your script should include the pauses. Where does your device wait, and for how long? You now know from Part C that this is a parameter you have to choose, not something that happens for free.

Script
[User detected near door → WAIT 0.5 s]
DEVICE: "Where are we going?"
[LISTEN up to 6 s | end-of-speech silence: 1.2 s]
USER:   "To class, I need to present today."
[WAIT 0.3 s]
DEVICE: "Are you presenting from your laptop or the class desktop?"
[LISTEN up to 8 s | end-of-speech silence: 1.5 s]
USER:   "I forgot!"
DEVICE: "No problem, I'll wait."
[WAIT up to 90 s for user to return; if door opens first, end silently]
[User returns → WAIT 1 s]
DEVICE: "Anything else you want me to remember for next time?"
[LISTEN up to 8 s | end-of-speech silence: 2.0 s]
USER:   "Remind me to bring my charger when I present."
DEVICE: "Got it. Good luck today!"

Process: I picked a moment when speaking is easier than using a screen: leaving the house in a rush with full hands. I sketched the storyboard, then wrote the dialogue. Next I listed other things the user might say, like "not now" or saying nothing, so the device knows how to respond to each. Last, I chose the wait times: short for easy questions, longer for questions that need more thought.

## E. Acting out the dialogue

Find a partner, and *without sharing the script with your partner* try out the dialogue you've designed, where you (as the device designer) act as the device you are designing. Please record this interaction (for example, using Zoom's record feature).
https://drive.google.com/file/d/10y4IMazRkMfGjkTr-8yvMTXaWIficM_O/view?usp=sharing
\*\***Describe if the dialogue seemed different than what you imagined when it was acted out, and how.**\*\*  
The dialogue was mostly similar to what I imagined. The main difference was that the participant sometimes gave answers that went beyond what I had written in the script. I had planned a few possible responses, but in the actual conversation I had to listen to what they said and decide which question to ask next. This made me realize that the device needs to handle more than a fixed sequence of questions, even when the overall interaction goes as planned.

---

# Lab 3 Part 2

For Part 2, you will redesign the interaction with the speech-enabled device using the data collected, as well as feedback from part 1.

## Prep for Part 2

1. What are concrete things that could use improvement in the design of your device? For example: wording, timing, anticipation of misunderstandings.

Feedback from Part 1 was that DoorBuddy was too slow and said more than it needed to. Someone leaving through the door is usually in a hurry, so extra words and long pauses cost them time. We made the device use fewer and simpler words and cut out the unnecessary introductions, so it says the same things in less time. We also shortened the pauses between turns so the conversation moves faster, while still giving the user enough time to finish what they are saying.

2. What are other modes of interaction *beyond speech* that you might also use to clarify how to interact? In particular: how does someone know when the device is listening, and when it is thinking? You have a screen and an LED.

The screen always shows what DoorBuddy is doing, using a short text label and a different background color for each state. It shows when the device is listening, when it is processing what the user said, and when it is speaking. The color can be seen at a glance from across the room, even when the user is busy grabbing their things, and the text makes the meaning clear for someone using it for the first time. This tells the user when it is their turn to talk and when they should wait. Without it, a user might start talking before the device is ready, or stand in silence not knowing whether the device heard them or is still thinking. With the screen, the user never has to guess what the device is doing.

3. Make a new storyboard, diagram and/or script based on these reflections.

The camera sees someone at the door.

Device: Where are you headed?

User: Class, I'm presenting.

Device: Got your laptop?

User: Oh no, I forgot!

Device: I'll wait.

The user comes back.

Device: Anything to remember next time?

User: My charger.

Device: Saved, charger. Good luck!

If the user says nothing or says not now, DoorBuddy says OK, bye and stays quiet.

4. (optional) Integrate [input devices](inputs.md) in the system

We used the webcam as our main input device, in two ways. First, the camera detects when someone walks up to the door, so the conversation starts on its own without the user pressing a button or saying a wake word. This matters because people leaving the house often have their hands full with a bag, keys, or a coffee. Second, the microphone records what the user says. The Pi listens for when the user has finished talking, turns their speech into text, and uses that text to decide what to say next. Together, the camera and microphone make the interaction completely hands free, so the user only has to talk.

## Prototype your system

The system should:
* use the Raspberry Pi
* use one or more sensors
* require participants to speak to it

*Document how the system works.*

*Include videos or screencaptures of both the system and the controller.*

https://drive.google.com/file/d/1gcnae5S60KLx6o51oWbBpJiQyQLoRRah/view?usp=sharing

## Test the system

Try to get at least two people to interact with your system. (Ideally, you would inform them that there is a wizard *after* the interaction, but we recognize that can be hard.)

Answer the following:

### What worked well about the system and what didn't?

At first, the system had trouble with the speech model. The model we started with was not accurate enough to catch what people were saying, and it sometimes stopped listening too early, before the user had finished answering. Switching to a bigger speech model fixed this, and the device could then understand users reliably and follow the conversation. The trade off is that a bigger model takes a little longer to process speech, so for a real product we would need to balance accuracy and speed.

### What worked well about the controller and what didn't?

The hardest part of the controller was timing and coordination. The wizard had to listen to the user, decide on the right response, and send it at the right moment, all while the conversation was happening. At first this made some responses come too late or feel out of place. After we rehearsed and planned which response to use in each situation, the wizard could respond quickly and the interaction went smoothly.

### What lessons can you take away from the WoZ interactions for designing a more autonomous version of the system?

The biggest lesson is how much timing matters. Even with a person controlling the device, it was hard to respond at the right moment, so an autonomous version needs to be good at deciding on its own when the user has finished talking and when to reply. We also learned that the speech model has to be accurate enough, since a model that mishears people or stops listening early breaks the whole conversation. Finally, the plan we made for the wizard, which listed what to say in each situation, is a good starting point for the autonomous version. Those planned responses can become the rules the device follows. We would also need to add responses for unexpected answers, since people do not always say what we expect.

### How could you use your system to create a dataset of interaction? What other sensing modalities would make sense to capture?

Every time someone uses DoorBuddy, the system could save a record of the whole conversation. This would include the audio of what the user said, the text it was turned into, what the device said back, and the timing of every turn, such as how long the user took to answer and how long each pause was. In our Wizard of Oz setup, the most useful part would be the wizard's choices. Each time the wizard picked a response to what the user said, that pairing shows what the right reply would have been, which is exactly what a more autonomous version would need to learn from. Over many sessions, the data would also show patterns, like where people usually go and which items they forget most often.

For other sensing modalities, a sensor on the door would tell us exactly when the user leaves or comes back, so each conversation would start and end at the right moment. The camera could capture more than whether someone is there, such as whether they are carrying a bag or a laptop, which could let the device skip questions it already knows the answer to. Time of day and the user's calendar would also help, since a class or meeting on the calendar tells the device what the user probably needs. Since this means recording people in their own home, everyone would need to agree to it and the data should stay on the device.

<details>
  <summary><strong>Submission Cleanup Reminder (Click to Expand)</strong></summary>

  **Before submitting your README.md:**
  - This readme.md file has a lot of extra text for guidance.
  - Remove all instructional text and example prompts from this file.
  - You may either delete these sections or use the toggle/hide feature in VS Code to collapse them for a cleaner look.
  - Your final submission should be neat, focused on your own work, and easy to read for grading.
</details>
