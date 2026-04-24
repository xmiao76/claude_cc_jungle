Act as a senior software architect and technical lead.

Create a step-by-step development plan for a Windows desktop Jungle board game application with a GUI and built-in AI so a human can play against the computer on a visual board.

Use the standard Jungle / Dou Shou Qi rules from this page as the main game specification and reference:
https://en.wikipedia.org/wiki/Jungle_(board_game)

If the board layout, terrain layout, or initial piece positions are unclear from the wiki page, also refer to:
https://veryspecial.us/free-downloads/AncientChess.com-DouShouQi.pdf

Do not restate the full rules in detail unless needed. Instead, refer to the source materials above and build the plan around implementing the ruleset correctly and consistently. If the sources mention ambiguous rules or variants, identify them, choose one clear standard interpretation, document it, and keep the implementation consistent.

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
- Support choosing who moves first before a game starts, including human first or AI first.

Rule clarification for river jumping:
- Implement the lion and tiger river-jump behavior using this explicit interpretation.
- The lion is stronger than the tiger for river jumping.
- The lion can jump across the river both horizontally and vertically.
- Horizontal lion jump means jumping across 3 river squares to the next non-water square on the opposite side.
- Vertical lion jump means jumping across 2 river squares to the next non-water square on the opposite side.
- The tiger can jump only vertically across 2 river squares to the next non-water square on the opposite side.
- Do not assume tiger has the same horizontal jump ability as lion unless the implementation explicitly supports it as an optional documented variant.
- Any rat-blocking behavior must still be handled correctly according to the selected ruleset.

UI requirements:
- The final UI must be polished and attractive, not just functional.
- The board should visually show river, trap, den, land, and other terrain clearly.
- Each piece should look like its animal, not just a letter or plain marker.
- Include good usability details such as piece selection highlights, legal move indicators, capture feedback, turn display, and win/loss messaging.
- Support flipping the board upside down as a view option. This feature must only rotate/flip the visual board orientation for display. It must not change the game state, must not swap sides internally, and must not change whose turn it is.
- Support a clear UI option to choose whether the human player or the AI moves first. This setting must affect only game start order and must work correctly together with the board-flip display option.
- Avoid placeholder-style visuals in the final release except optionally in debug mode.

Release requirements:
- Produce a packaged .exe in a release folder.
- The release folder must also include README.txt or README.md with launch, gameplay, controls, notes, and a clear statement identifying which model and which code agent were used to complete the task.
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
- suggested README.txt or README.md contents
- where prompt.md should be stored
- completion criteria

Completion is only achieved when the game is playable and stable, completes full games correctly, passes required automated tests, includes a tested packaged .exe in the release folder, includes README.txt or README.md with the model/code-agent statement, and includes prompt.md in the codebase.

