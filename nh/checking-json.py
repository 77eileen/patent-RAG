import os, glob
paths = [r'data\json_refine\20260129190307']
for p in paths:
    files = glob.glob(os.path.join(p, '**', '*.json'), recursive=True)
    print(f'{p}: JSON 파일 {len(files)}개')