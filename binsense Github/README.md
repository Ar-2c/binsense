
binsense GitHub/

├─ src/
│  ├─ classifier/                 # Steg 1 (MVP)
│  │  ├─ train\_resnet18.py
│  │  └─ eval\_metrics.py
│  └─ detection/                  # Steg 2 (YOLO)
│     ├─ yolo\_train.py            # wrapper runt Ultralytics/YOLOv5
│     └─ yolo\_infer.py
├─ notebooks/
│  ├─ 00\_explore\_data.ipynb
│  └─ 10\_resnet18\_mvp.ipynb
├─ configs/
│  ├─ classifier\_resnet18.yaml
│  └─ yolo.yaml                   # pekar på YOLO-dataset (se nedan)
├─ experiments/
│  ├─ classifier/                 # csv + figurer (små filer)
│  └─ detection/
├─ data/
│  ├─ classifier/                 # vårt nuvarande PyTorch-upplägg
│  │  └─ dataset/{Tom,Halvfull,Full,Overfull}/
│  └─ yolo/                       # för nästa fas (COCO-format)
│     ├─ images/{train,val,test}/
│     └─ labels/{train,val,test}/
├─ README.md
├─ requirements.txt               # inkluderar både classifier + yolo deps
├─ .gitignore
└─ .github/workflows/ci.yml       # enkel CI

