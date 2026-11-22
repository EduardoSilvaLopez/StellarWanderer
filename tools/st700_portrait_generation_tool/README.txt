ST-700 PORTRAIT GENERATION TOOL
===============================

What it does
------------
It generates portrait images on the Perchance AI image generator by itself,
batch after batch, and saves them as files in a folder you choose.

Each image is named:  <category>.<ethnicity>.<age>.<gender>.<N>.jpg
For example:          hydroponic.indonesian.young.androgyne.7.jpg

You do NOT have to click "OK", download a zip or sort files. The tool reads
each image directly from the page and gives it the right name.

For every group (for example "street, Indonesian, child, androgyne") it
tries to end up with 16 images. If you delete bad ones later and run the tool
again, it generates only what is missing and refills the gaps in the numbering.
It never overwrites an existing file.


QUICK START (the normal way, every time)
----------------------------------------
Step 1. Double-click   1_start_chrome.bat
        A new Chrome window opens. LEAVE IT OPEN until everything is done.
        (This is a separate Chrome with its own profile. Your normal Chrome is
        not touched and you do not need to log in anywhere.)

Step 2. Double-click   2_run_tool.bat
        A black window asks you five questions. Each one first SHOWS you all
        the available options. For every question you can type several
        options separated by commas, or type  All  for everything.

          1. Ethnic groups  Arab, Asian, black, Indian, Indonesian, Latino,
                            Sikh, white. Type for example  Arab,Indian  or  All.
                            You may also type a NEW name (e.g. Polynesian).
                            Required.
          2. Genders        male, female, androgyne.
                            Enter = androgyne.   All = all three.
          3. Categories     street, hydroponic, uniform.
                            Enter = All.
          4. Ages           child, teen, young, adult, mature, old.
                            Enter = each category's usual ages (street: child;
                            hydroponic: teen to old; uniform: young to old).
                            All = every age everywhere, which ALSO creates
                            "uniform teen".
          5. Folder         Enter = the portraits folder:
                            ...\StellarWanderer\commonesources\portraits
                            Or type/paste another folder. It is created if it
                            does not exist.

        Last, "Preview only?": type y to only SEE the plan and the prompts
        without generating anything. Press Enter to run for real.

        Typing All for ethnic groups means the 8 groups listed above (the list
        is in st700_portrait_templates.json, section "ethnicities").
        Careful: All ethnic groups x All genders is a LOT of work (see the
        time estimate the tool prints before it starts). Use the preview first.

Step 3. The tool shows the full plan: every group, how many images you
        already have, and the exact prompt it will use. This is your moment to
        check the prompts. Press ENTER to start, or close the window to cancel.

Step 4. Wait. Each group takes about 3 minutes (a full ethnic group of 10
        groups is about 30 minutes). Do not close the Chrome window and do not
        use that window. You can use your normal Chrome or other programs.
        Nothing needs clicking. When it ends it prints a summary table.

        When a batch ends, the tool asks "Generate another batch? [Y/n]".
        Press Enter (or y) to answer the five questions again for a new
        batch, without restarting anything. Type n to finish. The special
        Chrome window stays usable for the whole session.

Step 5. Look at the images and delete the ones you do not want. To replace
        them, just run the tool again with the same answers: it detects what is
        missing and generates only that.


WHAT YOU NEED INSTALLED (one time only)
---------------------------------------
- Windows with Google Chrome (already there).
- Python 3 (already installed on this computer).
- The Python package "playwright". Already installed on this computer.
  On another computer, open PowerShell once and type:
        python -m pip install playwright
  (You do not need to run "playwright install"; the tool uses your own Chrome.)


THE FOLDER FOR THE IMAGES
-------------------------
- The launcher (2_run_tool.bat) asks for it and proposes the portraits folder.
- If you run the Python file yourself without the --out option, it saves in
  the CURRENT folder of the window you ran it from.
- Images are saved under the lowest free number: if you have .1 to .16 and
  delete .3, the next run creates a new .3.


EDITING THE PROMPTS AND RULES
-----------------------------
Open  st700_portrait_templates.json  with Notepad. It contains:

  settings        art style (Casual Photo), shape (Portrait), images per batch
                  (16).
  categories      the prompt text for "street", "hydroponic" and "uniform", and
                  which ages each one covers. Words in {braces} are
                  placeholders that the tool fills in:
                    {ethnicity}  the name you typed, e.g. Indonesian
                    {article}    a / an, chosen automatically
                    {person}     the age + gender phrase, e.g. "young adult
                                 androgyne" or "10yo child"
                    {gender}     male / female / androgyne
                    {clothing}   see below
  person          how each age is worded (e.g. females are "young adult",
                  males are "young").
  clothing        hydroponic clothes by age (mature and old: blouse for
                  female, tube top for male).
  ethnicities     the list used by "All". Each line is  file tag : prompt word.
                  The tag is used in file names (latin), the word in the
                  prompt (Latino). Note black and white are lowercase in the
                  prompts, as in your earlier sets. Add a line to add a group.
  ethnic_rules    extra wording for particular ethnic groups. Currently:
                    - Arab and Indian, female and androgyne: prompt gets
                      "with uncovered hair," before the clothes and
                      "Her hair is visible." ("Their hair is visible." for
                      androgyne) at the end; negative prompt:
                      headscarf, hijab, veil, head covering.
                    - Indian, all genders: negative prompt: bindi.
                    - Sikh, young to old, all genders: "with a turban,". In
                      UNIFORM prompts the turban replaces the peaked cap
                      ("an olive turban with a red star on it").
                    - Sikh children and teens: no turban wording; negative
                      prompt: turban.
                  To change any wording, edit the text in the file.

                  ABOUT THE NEGATIVE PROMPT: Perchance has no visible box for
                  it, but every image request carries a "negativePrompt"
                  field. The tool puts the negative text there and prints
                  "negative prompt ... added to N generation request(s)" so you
                  can see it was sent. HOWEVER, in two test batches (a red hat
                  with negative "hat", and an apple with negative "red") the
                  generator showed no visible effect, so it may be ignored or
                  weak. Check the first results of each group. If a negative
                  does not work, the only reliable lever is the prompt text
                  itself (positive wording such as "with uncovered hair").
  gender_class    which gender uses which wording. Right now "androgyne" is
                  treated like "female" for age words and clothing, so mature
                  and old androgyne wear a blouse, and young androgyne is
                  "young adult androgyne". To get plain "young androgyne",
                  edit the "person" entry for "young" and add:
                       "androgyne": "young {gender}"
                  inside its braces.
  neutral_pronoun_genders
                  for these genders the words he/she/his/her/him are replaced
                  by they/their/them in the final prompt. (The current prompts
                  contain no pronouns, so this is only a safety net.)

Save the file, then run the tool with the preview option (y) to see the
resulting prompts before generating anything.


OPTIONS FOR ADVANCED USE (command line)
---------------------------------------
Open PowerShell in this folder and run, for example:

  python st700_portrait_generation_tool.py --ethnicity Indonesian --genders androgyne --dry-run

  --ethnicity   required. Names separated by commas, or All.
  --genders     default male,female,androgyne; or All
                (the .bat file proposes androgyne)
  --categories  default All (street,hydroponic,uniform)
  --list        print the available options and exit, for example:
                  --list ethnicities    (also: genders, categories, ages)
  --ages        for example teen,young, or All. By default each category uses
                its own ages (street: child only; hydroponic: teen, young, adult,
                mature, old; uniform: young, adult, mature, old).
                To also create "uniform teen", use:
                  --categories uniform --ages teen
  --target      images wanted per group (default 16)
  --batch-size  images per batch: 2, 4, 6, 8, 16 or 32 (default 16)
  --max-batches how many batches to try per group (default 3)
  --keep-extra  save every image even beyond the target
  --out         folder to save in (default: the current folder)
  --dry-run     only show the plan and prompts
  --yes         do not wait for Enter before starting
  --port        Chrome debugging port (default 9222)
  --timeout     seconds to wait for one batch (default 600)


IF SOMETHING GOES WRONG
-----------------------
"Cannot reach Chrome on port 9222"
    You did not run 1_start_chrome.bat, or its Chrome window was closed. Run
    1_start_chrome.bat again and leave the window open. If your normal Chrome
    is running it is fine; the tool uses the special window only.

"python is not recognized"
    Python is not installed or not on the PATH. Install Python from
    python.org and tick "Add Python to PATH" during installation.

The summary says "SHORT by N" for a group
    Some images never finished loading (a "Processing..." image can get
    stuck). Just run the tool again: it generates only what is missing.

"Generator frame not found" or similar errors
    The Perchance page may have changed or be temporarily down. Try again
    later. If it keeps failing, the tool needs an update.

The generation seems frozen
    A batch of 16 normally takes about 3 minutes. The tool prints
    "N/16 images ready..." every 15 seconds. It gives up on a batch after
    10 minutes and keeps what it got.

To stop the tool at any time: close its black window (or press Ctrl+C).
Images already saved stay in the folder.


NOTES
-----
- Everything runs in the special Chrome window. If you want to watch it work,
  look at that window, but do not click inside it while the tool is running.
- The prompts for male and female are exactly those used for the Indonesian
  set, so new sets match the old ones.
- Perchance is a free service: be patient, and do not run two copies of the
  tool at the same time.
