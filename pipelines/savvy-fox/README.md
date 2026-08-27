# Savvy Indigo Fox pipeline

This is the deliberately small production layer around HyperFrames. It keeps
the parts that worked in the first pilot and avoids requiring Archon, Claude,
or a large local language model.

## The contract

One JSON brief defines:

- the narration text and optional ElevenLabs settings;
- ordered video/image scenes;
- an optional pre-lip-synced opening whose original audio is preserved;
- background music at a controlled level;
- timed captions;
- the final MP4 path.

`project_dir` is resolved from the repository root. Scene, intro-audio, music,
narration, and output paths in the brief are then resolved relative to that
project directory. Absolute paths remain supported for local-only workflows.

## One-time setup

Create a virtual environment and install only the selected voice dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install elevenlabs python-dotenv
```

Copy the environment template and add the ElevenLabs values locally:

```bash
cp .env.example .archon/.env
```

Never commit `.archon/.env`. It is already ignored.

### GitHub Actions secret

For cloud rendering, fork this repository and open:

`Settings → Secrets and variables → Actions`

Create the repository secret `ELEVENLABS_API_KEY`. Then create the repository
variable `ELEVENLABS_VOICE_ID` with the chosen preset or cloned voice ID. The
workflow supplies safe defaults for the remaining tuning variables, which can
also be overridden as repository variables later.

The workflow can only render media that the runner can access. Commit small
assets, use Git LFS for larger clips, or keep media-heavy rendering local and
use GitHub Actions for narration generation only.

## Commands

Start from `pipelines/savvy-fox/brief.example.json`.

```bash
# Free and read-only: verify the brief and media paths
python scripts/savvy-fox.py check path/to/brief.json

# Spend voice credits only
python scripts/savvy-fox.py voice path/to/brief.json

# Rebuild video without calling ElevenLabs
python scripts/savvy-fox.py render path/to/brief.json

# Full build
python scripts/savvy-fox.py all path/to/brief.json
```

The split commands are intentional: caption, music, scene, and visual changes
never regenerate paid narration.

## Sustainable operating rhythm

1. Approve one short script.
2. Generate one narration.
3. Create three to five reusable 4–5 second character shots.
4. Change captions and assembly freely without spending voice credits.
5. Post before expanding the system.

Veo is best used for character acting and environmental action. HyperFrames and
FFmpeg handle timing, text, music, validation, and deterministic export.
