#!/bin/bash
conda-skeletor --git-url https://github.com/NSLS-II/metadatastore -gr v0.2.0 -o . -v
mv meta.yaml target.meta.yaml
