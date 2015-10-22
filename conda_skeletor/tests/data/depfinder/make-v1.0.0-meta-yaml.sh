#!/bin/bash
conda-skeletor --git-url https://github.com/ericdill/depfinder -gr v1.0.0 -o . -v
mv meta.yaml target.meta.yaml
