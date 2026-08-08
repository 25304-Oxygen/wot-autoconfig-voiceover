# Making Your Own Voice Pack

This document describes the format for third-party voice packs recognized by the
AutoConfigVoiceover plugin, and how to use its sound modification features.
Subtitles are only outlined here; the full details will be covered in the
Subtitle Engine guide.

> Convention: all JSON files accept `//` line comments (JSONC), so you can use
> comments to explain what each field means.

---

## 1. Overview

### 1.1 Where to install

Like any other wotmod, a voice pack takes effect when placed at:
`<World of Tanks install directory>/mods/<current version>/`

### 1.2 Directory structure

The general structure inside a wotmod is:

```
voiceover.wotmod/
└── res/
    ├── audioww/
    │   └── <path_to_your_bnk>/
    │       ├── voiceover.bnk              Audio bank (location given by `path` in pack.json)
    │       └── inbattle_communication_*.bnk   (optional; loaded automatically with voiceover.bnk)
    └── mods/
        └── voiceover/
            └── <pack_id>/
                ├── pack.json              ★ Required — the only required file
                ├── subtitles/             Subtitle subtree (optional; see the Subtitle Engine guide)
                │   ├── XXXstyles.json     The first valid .json file is treated as the style file
                │   ├── sentences/         Sentence files (file name = marker name embedded in the audio)
                │   └── images/            Root directory for subtitle images
                ├── bgimgs/                Menu background images (optional)
                │   ├── menu.png           Round icon (always follows the active voice pack)
                │   ├── panel.png          Rounded-rectangle panel background
                │   └── page.png           Square-corner panel background
                ├── icons/                 Left-side navigation button icons (optional)
                │   ├── settings.png       Settings icon
                │   ├── voice.png          Voice icon
                │   └── help.png           Help icon
                ├── events.json            Preview event list (optional; overrides the built-in list)
                ├── remap.json             Sound remapping table (optional; takes priority over audio_mods.xml)
                ├── audio_mods.xml         Sound remapping table (parsed in the official format)
                ├── attach.json            Sound binding scheme (optional)
                ├── info.html / info.txt   Voice pack info panel (optional)
                └── theme.json             Additional color theme (optional)
```

The directory name (`pack_id`) is the voice ID used for identification, switching,
and registration — a single voiceover.wotmod can contain multiple such directories.
The game engine's virtual file system (VFS) cannot handle paths containing
**non-ASCII characters**, so all file and folder names should be ASCII (English).

While scanning, the plugin only reads `pack.json` and validates/registers the bnk;
all other optional resources are parsed only when the voice is **activated**.

---

## 2. pack.json (required)

```json
{
    "path": "audioww/my_pack/voiceover.bnk",
    "name": "My Voice Pack"
}
```

| Key | Required | Meaning |
| :-- | :-- | :-- |
| `path` | Yes | VFS path to `voiceover.bnk`, starting from `res/` |
| `name` | Yes | Display name of the voice pack (shown in the menu/settings) |

- If either key is missing, or the bnk at `path` does not exist, the whole pack
  is skipped and a log entry is printed.
- If the `pack_id` collides with an existing in-game sound mode, registration is
  skipped (you can still override the built-in voiceover by choosing a suitable
  bnk path).

> Placing `voiceover.bnk` directly at the root of `audioww/` is also allowed (it
> will override the default voiceover), but this is not recommended.

---

## 3. Menu backgrounds and colors: bgimgs/ and icons/

A voice pack can supply custom menu images. When a file is missing, the
corresponding component keeps its default look.

| File | Menu component | Notes |
| :-- | :-- | :-- |
| `bgimgs/menu.png` | Round icon (toggles the menu open/closed) | **Always follows the currently active voice pack**, independent of the background icon scheme |
| `bgimgs/panel.png` | Rounded-rectangle panel background | Part of the background icon scheme; floats over the background color block |
| `bgimgs/page.png` | Square-corner panel background | Part of the background icon scheme; floats over the background color block |
| `icons/settings.png` | Left-side Settings nav button icon | Part of the background icon scheme; replaces the original color block |
| `icons/voice.png` | Left-side Voice nav button icon | Part of the background icon scheme; replaces the original color block |
| `icons/help.png` | Left-side Help nav icon | Part of the background icon scheme; replaces the original color block |

- These images are fixed to PNG format.
- The round icon `menu.png` is not part of the background icon scheme — it always
  comes from the currently active voice pack.

---

## 4. Preview event list events.json (optional)

Controls which events the **Preview** button on the settings page plays. The
format matches the plugin's built-in event list:

```json
[
    { "text": "Play when switching voice packs", "event": "vo_selected" },
    { "text": "Battle starts", "event": "vo_start_battle" }
]
```

| Key | Meaning |
| :-- | :-- |
| `text` | Text shown on the preview button |
| `event` | The Wwise event to play |

**If this file exists and has at least one valid entry, it replaces the entire
built-in event list** (no merging); if the file is missing or has no valid
entries, the plugin falls back to the built-in `playEvent.json`.

> When the relevant setting is enabled, `vo_selected` plays whenever you switch
> voice packs. You can change which sound is played using the
> [sound remapping](#5-sound-remapping-remapjson-optional) feature.

---

## 5. Sound remapping remap.json (optional)

Redirects game events to the voice pack's own events, switching dynamically
together with the active voice pack. `remap.json` is read first; if it is
missing, the plugin falls back to `audio_mods.xml` in the same directory
(parsed in the official format).

```json
{
    "vo_original_event": "vo_my_event",
    "vo_annoying": ""
}
```

- Each entry maps `"original event name"` to `"replacement event name"`.
- An **empty value** can be used to mute the event.
- Events not listed are left untouched.

Enable it by ticking **Allow sound remapping** on the settings page.

### audio_mods.xml (equivalent alternative file)

```xml
<!-- Form 1 -->
<root>
    <events>
        <event name="lightbulb" mod="lightbulb_mod"/>
        <event name="lightbulb_02" mod="mod_lightbulb_02"/>
    </events>
</root>
```

```xml
<!-- Form 2 -->
<root>
    <events>
        <event>
            <name>lightbulb</name>
            <mod>mod_lightbulb</mod>
        </event>
        <event>
            <name>lightbulb_02</name>
            <mod>lightbulb_02_mod</mod>
        </event>
    </events>
</root>
```

> The `<loadBanks>` section of the official format is ignored — the plugin does
> not yet have SFX sound-bank loading, switching, or management features.

---

## 6. Sound binding attach.json (optional)

Proactively plays **an extra voice line when a matching sound or command is
triggered** — for example, you can bind a line to the sound of your tank being
hit (ricochet, no-pen, or penetrated hits). This enriches the voice pack
experience.

```json
{
    "sound": [
        { "match": ["engine", "damaged"], "event": "vo_oops" },
        { "match": "vo_selected", "event": "vo_thanks", "strict": true }
    ],
    "cmd": [
        { "match": "affirmative", "event": "vo_affirm" }
    ]
}
```

| Key | Meaning |
| :-- | :-- |
| `sound` | Array of sound rules: triggered when the game plays a Wwise event |
| `cmd` | Array of command rules: triggered when **you** send a quick command |
| `match` | Keywords to match. A string or an array of strings; by default AND substring matching (case-insensitive) |
| `event` | Event name(s) to play on a match; a single name or an array (all played in sequence) |
| `strict` | Optional boolean. `true` requires the keyword to **exactly equal** the event name (useful for events/commands that share a prefix) |

Matching examples:

- `"match": ["engine", "damaged"]` → matches only when the event name contains
  both `engine` and `damaged` (AND).
- `"match": "affirmative"` (in `cmd`) → intercepts the client i18n key and
  matches if it contains `affirmative` (e.g. `#ingame_gui:chat_shortcuts/affirmative`).
- Multiple rules can match at once → all target events play in rule order.

Enable it by ticking **Allow sound binding** on the settings page.

> Note: not every sound effect can be bound. A few, such as the reload sound,
> are technically very hard to bind. For those, you can either create an event
> with the same name inside your `voiceover.bnk` to override the original, or
> use sound remapping.

---

## 7. Voice pack info info.html / info.txt (optional)

Rendered on the voice pack details page. **`info.html` takes priority; if
missing, it falls back to `info.txt`.**

> ★ **The first character is discarded**: the file's first character must be a
> **non-space** character. The engine tries to parse text starting with `<` as
> XML, which would make the read fail, so the first character acts as a *guard*
> and is dropped when read. Use an invisible character like `\0`, or a marker
> that won't affect display (e.g. `#`):

```
Actual file content:  \0<html><body><p>This is my voice pack</p></body></html>
Text read by plugin:  <html><body><p>This is my voice pack</p></body></html>
```

`info.html` content is rendered as rich text; `info.txt` as plain text.

> Common HTML escape characters:

| Character | Escape |
| :-- | :-- |
| & | `&amp;` |
| " | `&quot;` |
| < | `&lt;` |
| > | `&gt;` |

```
==== Example ====
Actual file content:  Ciallo～(∠．ω&lt; )⌒★
Rendered:             Ciallo～(∠・ω< )⌒★
(In World of Tanks, the "．" separator renders as "・".)
```

The `<p>` tag is the backbone of the rich text — all content must be inside a
`<p>` tag to be recognized. Supported HTML tags:

| Tag | Meaning | Usage |
| :-- | :-- | :-- |
| `<p>` | Paragraph | Attributes: `align="left\|center\|right"`, `size`, `color` |
| `<font>` | Adjust font size and color | Attributes: `size`, `color` |
| `<b>` | Bold | `<b>`**bold text**`</b>` |
| `<u>` | Underline | `<u>`<u>underlined text</u>`</u>` |
| `<a>` | Clickable hyperlink; no hover color change, no underline | `<a href="event:https://github.com">` link text `</a>` |
| `<img>` | Image | Must be the only content of a `<p>` block; a `<p>` containing `<img>` renders no text. Attributes: `align="left\|center\|right"`, `width`, `height` |

Supported image formats: `.jpg` and `.png` (not `.gif`).

> `<p align="center"><img src="mods/acv/image.png" width="200" height="100"/></p>`

| Attribute | Required | Meaning |
| :-- | :-- | :-- |
| `src` | Yes | Path; `mods/` is automatically converted to `../../` |
| `width` | No | Width in px; if omitted, uses the image's intrinsic width, capped at IMG_MAX_W with the aspect ratio preserved |
| `height` | No | Height; specifying both width and height stretches to the exact size |

---

## 8. Additional color theme theme.json (optional)

A voice pack can ship its own menu color theme, which then appears in the
**Color scheme** dropdown on the settings page.

```json
{
    "name":          "Dark Theme",
    "surface0":      "0x1E1E1E",
    "surface1":      "0x2D2D2D",
    "surface2":      "0x3C3C3C",
    "surface3":      "0x252526",
    "accent":        "0x3D6B9B",
    "accentHover":   "0x4D8BC5",
    "accentPress":   "0x2D5B7B",
    "stroke":        "0x888888",
    "textPrimary":   "0xD4D4D4",
    "textSecondary": "0x666666",
    "titleText":     "0xFFFFFF",
    "sbThumb":       "0x666666",
    "sbBtn":         "0x555555",
    "sbBtnArrow":    "0xCCCCCC"
}
```

- `name` is required (it's the label shown in the dropdown).
- Colors accept either `"#RRGGBB"` or `"0xRRGGBB"`.
- Undeclared slots automatically fall back to the default palette (Dark+), so
  you don't need to fill them all in.

| Slot | Purpose |
| :-- | :-- |
| `surface0` ~ `surface3` | Surface colors for panels, dialogs, inputs, dropdown rows |
| `accent` / `accentHover` / `accentPress` | Primary color, hover, pressed |
| `stroke` | Component outline |
| `textPrimary` / `textSecondary` | Body text / secondary text |
| `titleText` | Menu main title color |
| `sbThumb` / `sbBtn` / `sbBtnArrow` | Scrollbar thumb / button / arrow |

---

## 9. Subtitle subtree subtitles/ (optional)

A voice pack can carry subtitles so that text appears on screen when the voice
plays. For the full specification, see the **Subtitle Engine guide**. Only the
structure is listed here:

```
subtitles/
├── XXXstyles.json        Style file (the first valid .json in the directory); subtitles are disabled if absent
├── sentences/            Sentence files (file name = marker name embedded in the audio)
│   ├── <marker>.json
│   └── template.json     For the position-editing preview (optional; defaults to the first valid sentence file)
└── images/               Subtitle images (img paths in JSON are relative to this directory)
```

---

## 10. FAQ

**Q1: I placed the pack in `mods/<current version>/` but it doesn't show up in
the game?**

A: Check that `pack.json` has both keys, that the bnk path exists, and that the
`pack_id` doesn't collide with an existing in-game sound mode. Restart the game
after making changes.

**Q2: The voice plays but no subtitles appear?**

A: See the FAQ in the Subtitle Engine guide once it's published. The most likely
causes: the style file is missing or has no style section, the sentence file
name doesn't match the marker name embedded in the audio, or a file name
contains non-ASCII characters.

**Q3: Images don't show up?**

A: Check that the file names are pure ASCII (English) and that the paths match
what the JSON references (relative to `subtitles/images/`).

**Q4: Can built-in voices do all this?**

A: No. `mods/voiceover/` only scans third-party voice packs; built-in voices
have none of these optional resources, and the audio files in built-in voices
have no markers to begin with.
