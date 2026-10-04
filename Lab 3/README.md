# Chatterboxes

Feiyu (Morin) Zhou and Sirapop Umnakkittikul

# Part 1

## A. Text to Speech

**Write your own shell file to use your favorite of these TTS engines to have your Pi greet you by name.**

Script: [`speech-scripts/greet_morin_mig.sh`](speech-scripts/greet_morin_mig.sh). I used Piper (`en_US-lessac-medium`) with `--output-raw`, so playback starts while the rest of the sentence is still being synthesized.

```bash
(.venv) $ ./greet_morin_mig.sh
```

**Is the same greeting, in these different voices, the same greeting? Describe one concrete way the voice changed what the utterance seemed to mean or who seemed to be speaking.**

No. The words can be identical and the greeting still is not the same, because the voice tells you who is speaking and what kind of relationship they are claiming.

Concrete example: I said “Hi Morin and Mig. Welcome back.” with all three engines.

- **espeak** (`-ven+f2`) made it sound like a toy or an old GPS. The “welcome back” did not feel warm; it felt like a status message a machine is required to play.
- **festival** made the same line feel more like a person, but a slightly stiff, older male one. Because we had just heard it say the HAL line about Dave, the greeting picked up some of that “I am watching you” tone even though the words were friendly.
- **Piper / lessac** sounded like a calm American narrator. “Welcome back” suddenly meant *I know you, you have been here before*, closer to a host than a beep.

So the utterance’s meaning moved with the voice: system prompt vs. slightly ominous attendant vs. someone greeting you at the door. That is why we picked Piper for the greeting script — not only because it sounds better, but because it is the only one that actually felt like a greeting.

## B. Speech to Text

**Record a few seconds of your own speech and transcribe it with at least two model sizes. Report the real-time factor for each. At what point does the accuracy improvement stop being worth the delay, for a system that has to answer you?**

Recording: `speech-scripts/test.wav` (5 seconds of my own speech).

| Model | Transcript | Audio duration | Transcription time | Real-time factor |
| --- | --- | --- | --- | --- |
| `tiny.en` | Hi, this is Morin, I'm an interactive | 5.00s | 1.03s | **0.21x** |
| `base.en` | Hi, this is Morin. I'm in interactive. | 5.00s | 1.94s | **0.39x** |

Both are faster than real time (`tiny.en` transcribed 5s of audio in 1.03s; `base.en` took 1.94s). Model load is a one-time cost per process (`tiny.en` 0.55s, `base.en` 14.92s on first download). After that, only transcription time matters.

For a system that has to answer you, the accuracy improvement already stopped being worth it at `base.en`. It was almost **2× slower**, and it did not even fix the sentence: `tiny.en` heard “I'm **an** interactive,” `base.en` heard “I'm **in** interactive.” I would ship `tiny.en`, keep the model resident (as `listen.py` does), and design around leftover errors with a confirmation turn instead of waiting on a bigger model. `small.en` / `medium.en` would only add more delay.

**Write your own script that verbally asks for a numerical input and records the answer the respondent provides.**

Script: [`speech-scripts/ask_number.py`](speech-scripts/ask_number.py)

It uses Piper to ask for a five-digit zip code (you can make one up), records 6 seconds from the webcam mic, saves `zipcode_answer.wav`, and transcribes with faster-whisper.

```bash
(.venv) $ python ask_number.py
(.venv) $ python ask_number.py --model base.en
```

What I am listening for in the transcript: `oh` vs `zero`, missing digits, commas (`10,011` instead of `10011`), or the zip written as words (`nine four one oh three`). Those errors are why a later dialogue should confirm numbers instead of trusting the first transcript.

## C. Turn-taking: knowing when someone has stopped talking

**Try both extremes, and something in between. Describe what each one feels like to talk to. Note specifically: at 0.2s, what kinds of normal speech get cut off? At 1.5s, what does the delay make the system seem like?**

Same intended line each time: *I want a latte, um, actually a cappuccino.* `--min-silence` is turn-taking, not recognition.

**0.2s** — `[4.9s speech, 1.00s to transcribe] I want to say actually a cup of china`

It grabbed the turn the instant I stopped. I did not leave a long enough hole in the middle for it to split the sentence, so it did not cut me into two transcripts — it cut *inside* the words instead. The “um” / “latte” hesitation got eaten, and “cappuccino” became “cup of china.” At 0.2s, the speech that gets cut off is the small stuff in a repair: the filled pause, the word you are about to take back, the switch from first order to second. It feels jumpy, like someone finishing your sentence.

**0.4s (default)** — `[4.6s speech, 0.99s to transcribe] I want to take actually a cup of china`

Almost the same clip length and almost the same wait. It still feels like a short-order window: fine if the line is already in your mouth, still messy if you change your mind mid-sentence. “say” became “take.” This is the usable in-between for a command, not for thinking out loud.

**1.5s** — `[13.8s speech, 1.37s to transcribe] I don't want to let's hear it. Actually, I'll come with Cheena. What time is it?`

This is the one that changed how it *felt*. After I finished, nothing happened, so I kept going and even threw in a second question. The system treated all of that as one turn (13.8s of speech). The delay makes it seem like it did not hear me, or like a laggy phone call — vacant, a little deaf. The failure mode is not cutting you off; it is swallowing the next thing you say while you wait.

No correct value. A drink order wants ~0.4s so it can move after a short pause. Something that lets you think out loud needs closer to a second, or it will either clip the “actually…” or vacuum up “what time is it?” into the same utterance.

### The complete loop

With `echo_bot.py` at the default 0.4s endpointing, it heard `I want to cover the tape` (still the cappuccino line, even more mangled) and said `You said: I want to cover the tape.` Timing: **asr 1.01s | tts first audio 0.28s | total gap 1.29s**. Piper itself was quick; the dead air was almost all Whisper. Even with a “fast” endpoint, you still wait more than a second before the device talks back — and that gap is what feels like the system thinking.

## D. Storyboard

**Post your storyboard and diagram here.**

<img width="1699" height="906" alt="image" src="https://github.com/user-attachments/assets/f9f3ad08-f3bf-48f5-8dc1-8bb0bd1049b1" />

Concept: DoorBuddy. DoorBuddy is a speech device by the front door. When you approach with a bag, it asks where you're going and follows up with a targeted question to catch anything you forgot. Afterward, it asks if there's anything new to remember next time.

Storyboard: The user heads for the door with a bag. DoorBuddy asks, "Where are we going?" The user says they're presenting in class. DoorBuddy asks whether they're using their laptop or the class desktop. The user freezes, realizes the laptop isn't in the bag, and runs back for it. When they return, DoorBuddy asks if there's anything else to remember for next time.

**Please describe and document your process.**

Script:

```text
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
```

Process: I picked a moment when speaking is easier than using a screen: leaving the house in a rush with full hands. I sketched the storyboard, then wrote the dialogue. Next I listed other things the user might say, like "not now" or saying nothing, so the device knows how to respond to each. Last, I chose the wait times: short for easy questions, longer for questions that need more thought.

## E. Acting out the dialogue

Video of the acted-out dialogue: [Google Drive](https://drive.google.com/file/d/10y4IMazRkMfGjkTr-8yvMTXaWIficM_O/view?usp=sharing)

**Describe if the dialogue seemed different than what you imagined when it was acted out, and how.**

The dialogue was mostly similar to what I imagined. The main difference was that the participant sometimes gave answers that went beyond what I had written in the script. I had planned a few possible responses, but in the actual conversation I had to listen to what they said and decide which question to ask next. This made me realize that the device needs to handle more than a fixed sequence of questions, even when the overall interaction goes as planned.

---

# Part 2

## Prep for Part 2

1. What are concrete things that could use improvement in the design of your device? For example: wording, timing, anticipation of misunderstandings.

Most of the feedback on DoorBuddy in Part 1 was that it was slow and talked too much. That makes sense: people are usually in a hurry when they leave the house, and nobody wants to stand at the door listening to a long greeting. So for Part 2 we rebuilt it as the **One More Thing Bag**. It still asks where you're going, but it skips the small talk and goes straight to the question that might save you a trip back. We also cut the pause it waits for before replying, from 1.2–2.0 s in our Part 1 script down to 0.8 s. In our tests that was still enough time to say something like "Class, I'm presenting" without getting cut off.

2. What are other modes of interaction *beyond speech* that you might also use to clarify how to interact? In particular: how does someone know when the device is listening, and when it is thinking? You have a screen and an LED.

In Part 1, people often weren't sure whether it was their turn to talk. Now the color screen always shows one of four states, each with its own color and a short hint:

- **READY** (blue): "Step up to start."
- **LISTENING** (green): "Talk to me now. Pause when you're done."
- **THINKING** (orange): "Got it. One moment..."
- **SPEAKING** (purple): "Listen to me. Answer when it's green."

You can tell the color from a few steps away, even while looking for your keys, and the text helps the first time someone uses it. Green always means go ahead and talk. Any other color means the bag isn't listening, so talking over it won't do anything.

3. Make a new storyboard, diagram and/or script based on these reflections.

Here is a typical run with the lines the bag actually uses (they're all in [`wizard/dialogue.py`](wizard/dialogue.py)):

> *The wizard sees someone walk up on the camera and presses Start.*
>
> **Bag:** Hi! Before you head out, where are you going today?
> **User:** Class, I'm presenting.
> **Bag:** Are you presenting from your own laptop, or the classroom computer?
> **User:** My own laptop.
> **Bag:** Do you have your laptop charger with you?
> **User:** Oh no, I forgot it!
> **Bag:** No problem, go grab it. I'll be here.
>
> *The user comes back, and the wizard picks the next line.*
>
> **Bag:** Is there anything you want me to ask about next time?
> **User:** My charger.
> **Bag:** Okay, I'll ask about that next time.

If nobody answers, the bag asks once more ("I didn't hear anything. Where are you headed today?"). If there's still no answer, the wizard ends it with "Sounds like you're set. Have a great day!" or just presses Stop.

4. (optional) Integrate [input devices](inputs.md) in the system

We added the webcam as an extra sensor. The wizard uses the live video to see when someone comes up to the door and starts the conversation from there. There's also an optional auto-start mode where the bag starts by itself when the camera sees steady movement. That's closer to how a real product would work, since people heading out usually have their hands full. The webcam's microphone is what the bag listens with. The Pi figures out when the user has stopped talking, turns what they said into text, and sends it to the wizard, who picks the reply. Other than two buttons we use while testing, the participant doesn't have to touch anything.

## Prototype your system

### How the One More Thing Bag works

The whole thing is one program on the Pi, [`wizard/bag_wizard.py`](wizard/bag_wizard.py). It reads the webcam and microphone, works out when the participant has finished talking, transcribes the answer, speaks the bag's replies and updates the screen. It also runs a small web page for the wizard, who keeps it open on a laptop the participant can't see.

| Part | Hardware | What it does |
| --- | --- | --- |
| Participant screen | Mini PiTFT (ST7789, 240×135) | Shows READY, LISTENING, THINKING or SPEAKING with a short hint |
| Ears | The webcam's built-in microphone | Silero VAD finds the end of each turn; NVIDIA Parakeet TDT 0.6B turns it into text |
| Voice | USB speaker | Piper (`en_US-lessac-medium`) speaks the replies |
| Eyes | Full HD USB webcam (`/dev/video0`) | Live video and a motion hint, only shown to the wizard |
| Controller | Any laptop browser at `http://<pi-ip>:5000` | Camera view, transcript, current state, reply buttons and a box for typing replies |

**What the bag does on its own.** It decides you're done talking after 0.8 s of silence (the wizard can change this during a session). Each answer is transcribed and shows up for the wizard in about half a second, and if nobody says anything for 12 s it lets the wizard know. The camera reports movement as "someone may be in view". It's just a hint: it doesn't actually recognize people, so someone walking past or the lights changing can set it off. On its own it doesn't start anything. With auto-start on (`--auto-start`, or the checkbox on the controller), about half a second of steady movement while the bag is READY starts the conversation. Afterwards it waits 15 s before it can start again, so it doesn't greet the same person twice.

**What the wizard does.** The wizard decides when to start, unless auto-start or the PiTFT buttons are on (`--buttons`: A starts, B stops). After each answer, the wizard picks what the bag says next. The prepared follow-ups are grouped by where the person is going (class, gym, travel, work and errands, general, wrap up). The **Wrap up** lines end the conversation and put the bag back to READY. If none of them fit, the wizard can type a reply and the bag will say it. There are also four buttons for when things go wrong:

- **Clarify** asks the participant to say it again, a little slower.
- **Repeat my last line** says the bag's last line again.
- **Didn't hear anything** asks again when nobody answered.
- **I can't see inside** handles questions like "Is my charger in there?"

**Stop / Reset** stops the bag, puts it back to READY and clears the transcript. We press it between participants. Button B on the PiTFT also stops the bag, but it keeps the transcript.

**Taking turns and privacy.** The bag only listens while the screen is green. While it's talking, and for 0.3 s after, it ignores the microphone so it doesn't transcribe its own voice. Video frames and audio stay in memory and are never saved to disk. The transcript only lives on the controller page and is gone when the program stops. The bag also never pretends it can see inside itself or knows what's packed. Every line is a question or a reminder ("Do you have your laptop charger with you?"), and if someone asks it to check, the wizard uses **I can't see inside**.

**Why we changed the speech recognizer.** On our first run, the Part 1 recognizer (Whisper `tiny.en`) kept cutting answers off ("I'm going to...") and, when the audio was noisy, got stuck repeating itself ("I can't talk about it. I can't talk about it. ..."). Once it took 8.5 s to transcribe 2 s of speech. Some of this was the microphone's fault: its gain was turned all the way up (+24 dB), so even a quiet room was clipping. Turning it down to +12 dB (`wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 0.63`) dropped the background level from 0.37 to 0.05 and got rid of the clipping. Then we tried four recognizers on the Pi 5 with the same recordings:

| Recognizer | Time per second of audio | Our Part 1 recording, `test.wav` |
| --- | --- | --- |
| Whisper `tiny.en` (Part 1) | ~0.2 s | "Hi, this is Morin, I'm an interactive" |
| Whisper `base.en` | ~0.4 s | "Hi, this is Morin. I'm in interactive." |
| Moonshine base | ~0.1 s | "Hi, this is Maureen, and I'm Interactive Deputy." |
| **Parakeet TDT 0.6B** (now used) | ~0.1 s | "Hi, this is Mauren. I'm in Interactive Development." |

We went with Parakeet. It was about twice as fast as `tiny.en` and gave the most complete sentences. It also doesn't build its answer word by word the way Whisper does, so it can't get stuck in a loop. It still misspells names ("Mauren"), but the bag only needs to catch places and items, so that's fine. Whisper is still there for comparison (`--asr whisper`).

**Videos.** We recorded two videos of the same session at the same time:

- **The conversation with Mig:** [Google Drive](https://drive.google.com/file/d/1gcnae5S60KLx6o51oWbBpJiQyQLoRRah/view?usp=sharing). Mig talks to the bag and the bag answers.
- **The wizard's side:** [Google Drive](https://drive.google.com/file/d/1nUXZJfdLnNEPj9l5kvPjdtuLFRno9VLv/view?usp=drive_link). This shows the wizard using the controller page during that conversation. It has no sound, but it lines up exactly with the video above, so you can play them side by side and see each answer show up in the transcript and which reply the wizard picked.

#### Running it on the Pi

The Pi gets a new IP address every time it boots. You can read it off the PiTFT before stopping the boot screen, or run `hostname -I` on the Pi.

```bash
ssh pi@<pi-ip>
cd ~/Interactive-Lab-Hub/Lab\ 3
source .venv/bin/activate
pip install -r requirements.txt                 # OpenCV, Pillow and the PiTFT libraries
cd speech-scripts && ./setup.sh && cd ..        # only if models/ or voices/ is missing
sudo systemctl stop piscreen.service            # the Lab 2 boot screen holds the PiTFT until the next reboot
wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 0.63    # webcam mic at +12 dB; 1.0 clips
cd wizard
./get_asr_models.sh                             # once: downloads Parakeet (~630 MB)
python bag_wizard.py                            # add --buttons to use the PiTFT buttons
```

When it starts, `bag_wizard.py` prints the controller address (`Wizard controller: http://<current-ip>:5000`). Open that on a laptop on the same network and keep the laptop where the participant can't see it. The page has no password, so only use it on a network you trust.

Other options: `--min-silence 1.0` (end-of-turn silence), `--auto-start`, `--camera /dev/video2`, `--mic 2 --speaker 1` (an index or part of the device name, as listed by `test_mic.py` and `test_speaker.py`), `--no-camera`, `--no-screen`, `--asr whisper --whisper-model base.en`, `--port 8000`.

#### Testing each part on its own

Run these from `Lab 3/wizard` with the virtual environment active:

| Part | Command | It works if |
| --- | --- | --- |
| Screen | `python test_screen.py` | The four states show for 2 s each. (`--save` writes them as PNGs, no Pi needed.) |
| Webcam | `v4l2-ctl --list-devices`, then `python test_camera.py --camera 0` | It prints `ok=True`. Waving a hand gives `someone_in_view=True`, and keeping it moving gives `sustained=True`, which is what auto-start uses. |
| PiTFT buttons | `python test_buttons.py` | Pressing A and B prints `button A pressed` and `button B pressed`. |
| Microphone | `python test_mic.py` | The level bar moves when you talk, and your sentence gets transcribed after a 0.8 s pause. |
| Speaker | `python test_speaker.py` | You hear the opening question. |

If something doesn't work:

- **The mic level stays near 0:** unmute it with `wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0`, or turn it up in `alsamixer` (see [prep.md](prep.md)).
- **No sound, and `wpctl status` only lists `Dummy Output`:** the Pi can't find the speaker. Plug it in and check that it shows up in `lsusb` and `aplay -l`.
- **The program prints `[screen] could not open the PiTFT`:** check that SPI is on (`ls /dev/spidev*`).
- **The screen flickers between our states and the Lab 2 clock:** `piscreen.service` is still running. Stop it with `sudo systemctl stop piscreen.service`.

## Test the system

### What worked well about the system and what didn't?

Speech recognition was the weak spot at first. The Part 1 model, Whisper `tiny.en`, often got people's answers wrong, cut them off halfway, and on noisy audio kept repeating the same phrase. When that happened the wizard had no idea what the person had actually said, and the conversation fell apart. We fixed it in two steps: we turned the webcam mic down (it was so loud it distorted speech), and we switched to Parakeet, a bigger and more accurate model. After that the bag understood people pretty reliably. "I'm going to play football." came through in full in about a third of a second. We expected the bigger model to be slower, but it was actually faster than the old one. The downsides are the big download (about 630 MB) and a few seconds of loading when the program starts.

### What worked well about the controller and what didn't?

Timing was the hardest part for the wizard. You have to read the transcript, pick a reply and send it while the person is standing there waiting. Early on, some replies came too late or didn't really match what the person said. Practicing helped a lot, and so did deciding ahead of time what to say in each situation. Since the prepared lines are grouped by destination, most replies only take one click. Typing a custom reply is still the slowest, so we only did that for answers the script didn't cover.

### What lessons can you take away from the WoZ interactions for designing a more autonomous version of the system?

Mostly, that timing really matters. Even with a person in control it was hard to reply at the right moment, so an autonomous version would need to be good at telling when the user is done talking and when to answer. Speech recognition also has to be good enough. If it mishears people or stops listening too early, the whole conversation breaks. The plan we wrote for the wizard, with what to say in each situation, would be a good starting point. Those responses could turn into rules the device follows, but it would still need some way to handle answers we didn't plan for, because people say all kinds of things.

### How could you use your system to create a dataset of interaction? What other sensing modalities would make sense to capture?

Right now the prototype doesn't save anything, but the controller page already has everything you'd want to log. If participants agree, we could save each session: what the user said (as text, plus audio if they're OK with it), what the bag said back, and how long each turn and pause took. The most useful part would be the wizard's choices. Each time the wizard picked a reply to something a user said, that's an example of the right response, which is what an autonomous version would need to learn from. Over many sessions, the data would also show things like where people usually go and what they forget most often.

Other sensors would help too. A door sensor would tell us exactly when someone leaves or comes back, so conversations would start and end at the right time. The camera could pick up more than just movement, like whether someone is already carrying a laptop, so the bag wouldn't ask about it. Time of day and the user's calendar would also be useful, since a class or meeting coming up says a lot about what they'll need. Since all of this means recording people at home, everyone would have to agree to it, and the data should stay on the device.
