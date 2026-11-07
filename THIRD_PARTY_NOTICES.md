# Third-Party Notices

## youtube-niche-finder

ViralTrack runs youtube-niche-finder (https://github.com/pandich93/youtube-niche-finder) as its YouTube
foundation. It is included unmodified as a git submodule in `upstream/youtube-niche-finder`. Its license
file is `upstream/youtube-niche-finder/LICENSE`:

```
MIT License

Copyright (c) 2026 Fozil Umarov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The JSON files in `tests/fixtures/niche_finder/` were recorded from that software running on its synthetic
demo seed (`backend/tests/seed_demo.py`).

Dependency and model licenses are listed in `docs/phase-1/OPEN_SOURCE_ADOPTION_AUDIT.md`.

## shadcn-admin

The web UI in `web/` is adapted from shadcn-admin (https://github.com/satnaing/shadcn-admin), commit
`e16c87f213a5ba5e45964e9b67c792105ec74d26`, with its demo features, demo authentication and Clerk integration
removed (see `docs/phase-4-7/FRONTEND_PHASE_1_REPORT.md`). Its license file is kept as `web/LICENSE`:

```
MIT License

Copyright (c) 2024 Sat Naing

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The shadcn/ui components it contains (`web/src/components/ui`) come from shadcn/ui
(https://github.com/shadcn-ui/ui, MIT, Copyright (c) 2023 shadcn). npm dependencies keep their own licenses in
`web/node_modules`; the license summary is in the phase 1 report.
