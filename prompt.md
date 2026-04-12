Act as a senior software architect and technical lead.

Create a step-by-step development plan for a Windows desktop Jungle board game application with a GUI and built-in AI so a human can play against the computer on a visual board.

Use the standard Jungle / Dou Shou Qi rules from this page as the game specification and reference:
https://en.wikipedia.org/wiki/Jungle_(board_game)

Do not restate the full rules in detail unless needed. Instead, refer to the wiki page and build the plan around implementing that ruleset correctly and consistently. If the wiki page mentions ambiguous rules or variants, identify them, choose one clear standard interpretation, document it, and keep the implementation consistent.

Requirements:
- Choose the best programming language, architecture, Windows GUI framework, and AI approach.
- All source code must be newly written for this application.
- Phase 1 must deliver a working GUI where a human can play against the AI.
- The engine must be responsive and suitable for smooth local play.
- The app must be easy to build, run, test, and package locally.
- Testing must be integrated throughout development.
- Automated tests must be created and maintained during development.
- Bugs found in testing or gameplay must be fixed and regression-tested until stable.
- The final application must complete full Jungle games correctly.
- AI-vs-AI mode is desirable if practical.

UI requirements:
- The final UI must be polished and attractive, not just functional.
- The board should visually show river, trap, den, land, and other terrain clearly.
- Each piece should look like its animal, not just a letter or plain marker.
- Include good usability details such as piece selection highlights, legal move indicators, capture feedback, turn display, and win/loss messaging.
- Avoid placeholder-style visuals in the final release except optionally in debug mode.

Release requirements:
- Produce a packaged .exe in a release folder.
- The release folder must also include README.txt with launch, gameplay, controls, and notes.
- The packaged .exe must be tested after packaging, not only during development.
- If packaging defects are found, fix, rebuild, and retest until the packaged executable passes.
- Save this prompt as prompt.md in the codebase.

Please provide:
- recommended tech stack and justification
- architecture and module breakdown
- phased roadmap
- test plan for each phase
- automated testing strategy
- AI/engine strategy
- performance optimization plan
- local build, run, and test workflow
- bug-fix and regression-test workflow
- packaging plan
- release validation plan
- expected release folder contents
- suggested README.txt contents
- where prompt.md should be stored
- completion criteria

Completion is only achieved when the game is playable and stable, completes full games correctly, passes required automated tests, includes a tested packaged .exe in the release folder, includes README.txt, and includes prompt.md in the codebase.
