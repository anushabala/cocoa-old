# Prerequisite

Latest Tensorflow (bleeding-edge version). If you're on the NLP cluster, you can run it on Ubuntu machines (e.g. john) by `source activate /u/hehe/tf-latest-cpu`.  

Initialize:

    mkdir output

Generate scenarios from the schema:

    python src/basic/generate_scenarios.py --schema-path data/friends-schema.json --scenarios-path output/friends-scenarios.json --num-items 5 --num-scenarios 10

Generate dataset of dialogues:

    python src/basic/generate_dataset.py --schema-path data/friends-schema.json --scenarios-path output/friends-scenarios.json --train-examples-paths output/friends-train-examples.json --test-examples-paths output/friends-test-examples.json --train-max-examples 10

Train a model:
    
    make scenarios; make dataset; make train model={encdec, attn-encdec, attn-copy-encdec}
