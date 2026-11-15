"""Summarize a completed identity trial without asserting identity accuracy."""
import argparse
import collections
import json
from pathlib import Path
import cv2


def iou(a,b):
    x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]))
    intersection=x*y
    return intersection/max(1e-8,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
    data=json.loads((args.directory/'report.json').read_text(encoding='utf-8'));rows=data['detections']
    ids=collections.Counter();counts=collections.Counter();reasons=collections.Counter();changes=[];previous=[];pending=0;transitions=0
    for row in rows:
        faces=row['faces'];counts[len(faces)]+=1
        ids.update(face['person'] for face in faces if face['person'] is not None)
        pending+=sum(face['person'] is None for face in faces)
        reasons.update(face.get('reason',face['status']) for face in faces)
        # Geometric continuity is a review aid, not ground-truth identity tracking.
        pairs=sorted(((iou(a['box'],b['box']),i,j) for i,a in enumerate(previous) for j,b in enumerate(faces)),reverse=True)
        used_a=set();used_b=set()
        for score,i,j in pairs:
            if score<.7:break
            if i in used_a or j in used_b:continue
            used_a.add(i);used_b.add(j)
            if previous[i]['person']!=faces[j]['person'] and (previous[i]['person'] is None or faces[j]['person'] is None):
                transitions+=1
            if previous[i]['person'] is not None and faces[j]['person'] is not None and previous[i]['person']!=faces[j]['person']:
                changes.append({'frame':row['frame'],'seconds':round(row['frame']/data['fps'],3),
                                'before':previous[i]['person'],'after':faces[j]['person'],'iou':round(score,3)})
        previous=faces
    video=cv2.VideoCapture(str(args.directory/'review.mp4'));decoded=0
    while video.grab():decoded+=1
    video.release()
    summary={'processed_frames':len(rows),'decoded_review_frames':decoded,'complete_review':decoded==len(rows),
             'duration_seconds':len(rows)/data['fps'],'candidate_ids':len(ids),'face_count_distribution':dict(sorted(counts.items())),
             'total_face_detections':sum(ids.values())+pending,'assigned_face_detections':sum(ids.values()),'pending_face_detections':pending,'reason_counts':dict(reasons),'pending_assigned_transitions':transitions,'top_ids_by_frames':ids.most_common(20),
             'ids_in_at_most_3_frames':sum(n<=3 for n in ids.values()),
             'adjacent_high_overlap_id_change_count':len(changes),'adjacent_high_overlap_id_change_examples':changes[:30],
             'inference_ms_median':data['inference_ms_median'],'inference_ms_p95':data['inference_ms_p95'],
             'interpretation':'Overlap-based ID changes flag locations for manual review. Neither ID counts nor face counts establish true people counts, missed faces, switches or accuracy.'}
    (args.directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if not summary['complete_review']:raise RuntimeError('Review video frame count mismatch')

if __name__=='__main__':main()
