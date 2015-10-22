#!/bin/bash
conda-skeletor --git-url https://github.com/scikit-xray/scikit-xray -gr v0.0.5 -o . -v
mv meta.yaml target.meta.yaml
