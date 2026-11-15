"""Research-only appearance association; no motion tracking or identity guarantee."""
import numpy as np


class IdentityGallery:
    def __init__(self, threshold=.50, margin=.10, enroll_threshold=.40, confirmations=5, max_templates=6):
        if not 0<=enroll_threshold<=threshold<=1 or not 0<=margin<=2:
            raise ValueError('Require 0 <= enroll_threshold <= threshold <= 1 and margin in [0,2]')
        if confirmations<1 or max_templates<1:raise ValueError('Positive confirmations and template bound required')
        self.threshold=threshold;self.margin=margin;self.enroll_threshold=enroll_threshold
        self.confirmations=confirmations;self.max_templates=max_templates
        self.people=[];self.pending=[];self.frame=0

    def scores(self, vector):
        # Competing scores are between PERSON groups, never between their templates.
        return sorted(((max(float(vector@t) for t in templates), i) for i,templates in enumerate(self.people)),reverse=True)

    def update(self, vectors, qualities):
        self.frame+=1
        self.pending=[p for p in self.pending if self.frame-p['last']<=3]
        ranked=[self.scores(v) for v in vectors]
        result=[{'person':None,'status':'pending','reason':'low_similarity','similarity':None} for _ in vectors]
        proposals=[]
        for i,scores in enumerate(ranked):
            best=scores[0][0] if scores else -1.;second=scores[1][0] if len(scores)>1 else -1.
            result[i]['similarity']=best if scores else None
            if best>=self.threshold and best-second>=self.margin:
                proposals.append((best,i,scores[0][1],best-second))
            elif best>=self.enroll_threshold:result[i]['reason']='ambiguous_person'
        reserved=set()
        for score,i,identity,gap in sorted(proposals,reverse=True):
            if identity in reserved:
                result[i]['reason']='same_frame_conflict';continue
            reserved.add(identity)
            result[i]={'person':identity+1,'status':'matched','reason':'person_match','similarity':score}
            templates=self.people[identity]
            # Keep the enrollment anchor; add only confident, sufficiently distinct poses.
            if (self.max_templates>1 and qualities[i] and score>=.60 and gap>=.15 and score<.90
                    and float(vectors[i]@templates[0])>=.45):
                if len(templates)<self.max_templates:templates.append(vectors[i].copy())
                else:templates[1:]=templates[2:]+[vectors[i].copy()]
        used_pending=set();enroll=[]
        for i,vector in enumerate(vectors):
            if result[i]['person'] is not None:continue
            if not qualities[i]:result[i]['reason']='low_quality';continue
            best=ranked[i][0][0] if ranked[i] else -1.
            # Ambiguity and reservation conflicts MUST NOT create new people.
            if result[i]['reason'] in ('ambiguous_person','same_frame_conflict') or best>=self.enroll_threshold:continue
            candidates=sorted(((float(vector@p['anchor']),j) for j,p in enumerate(self.pending)
                               if j not in used_pending and self.frame-p['last']<=1),reverse=True)
            if candidates and candidates[0][0]>=.65 and (len(candidates)<2 or candidates[0][0]-candidates[1][0]>=.10):
                j=candidates[0][1];p=self.pending[j];p['hits']+=1;p['last']=self.frame
            else:
                j=len(self.pending);p={'anchor':vector.copy(),'hits':1,'last':self.frame};self.pending.append(p)
            used_pending.add(j)
            result[i]['reason']='awaiting_confirmation'
            if p['hits']>=self.confirmations:enroll.append((i,j,vector))
        for i,j,vector in enroll:
            # Recheck against people enrolled earlier in this frame.
            scores=self.scores(vector)
            if scores and scores[0][0]>=self.enroll_threshold:continue
            self.people.append([self.pending[j]['anchor'].copy()])
            result[i]={'person':len(self.people),'status':'enrolled','reason':'confirmed_new_person','similarity':None}
            self.pending[j]['last']=-100
        # Hard bound provisional storage; pending candidates never become public IDs.
        self.pending=sorted((p for p in self.pending if self.frame-p['last']<=3),key=lambda p:p['last'],reverse=True)[:64]
        return result
