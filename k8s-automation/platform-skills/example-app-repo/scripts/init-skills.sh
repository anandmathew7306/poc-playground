#!/bin/bash
# Run once after cloning a new project repo
# Pins skills to the approved release tag

SKILLS_TAG=${1:-"v1.0.0"}

echo "Initialising platform-skills at tag $SKILLS_TAG"

git submodule add \
  git@github.com:[org]/platform-skills.git \
  .cursor/skills

cd .cursor/skills
git checkout tags/$SKILLS_TAG
cd ../..

git add .gitmodules .cursor/skills
git commit -m "chore: pin platform-skills to $SKILLS_TAG"

echo "Done. Skills available at .cursor/skills/"
echo "Run 'git submodule update --init' after cloning on any new machine."
