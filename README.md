# claude-skills
A Repo containing the Claude Skills i use personally to build, test and ship.

## SKILL.md template
Each skill should have a `SKILL.md` file describing:
- name
- description
- when to invoke
- how to run it (including flags)
- what the user sees (the output, UX, etc.)
- why the design is the way it is (optional, but helpful for future maintenance and contributors)

## How to add a new skill
1. Fork the repo
2. Create a new branch for your skill
3. Add a new directory with your skill's name. Inside that directory, create a `SKILL.md` file following the template above.
4. Implement the skill's functionality as described in your `SKILL.md`. You can add any necessary scripts, assets, or documentation within the same directory.
5. Test your skill thoroughly to ensure it works as expected.
6. Commit your changes and push the branch to your forked repo
7. Open a pull request to merge your skill into the main repository, providing a clear description of what your skill does and any relevant details for reviewers.