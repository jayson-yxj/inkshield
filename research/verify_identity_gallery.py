"""Focused regression checks for identity enrollment failure modes."""
import numpy as np
from identity_gallery import IdentityGallery


def v(x,y):
    a=np.array([x,y],dtype=np.float32);return a/np.linalg.norm(a)


def main():
    g=IdentityGallery();a=v(1,0)
    for _ in range(4):assert g.update([a],[True])[0]['person'] is None
    assert g.update([a],[True])[0]['person']==1
    # Duplicate templates belonging to ONE person do not compete for the margin.
    g.people[0].append(a.copy())
    for _ in range(100):assert g.update([a],[True])[0]['person']==1
    assert len(g.people)==1
    # Different people with indistinguishable appearance stay pending, never proliferate.
    g.people.append([v(.99,.1)])
    for _ in range(100):assert g.update([a],[True])[0]['person'] is None
    assert len(g.people)==2
    g=IdentityGallery();g.people=[[a]]
    result=g.update([a,a],[True,True]);assert sum(r['person']==1 for r in result)==1
    assert len(g.people)==1
    for _ in range(10):g.update([v(0,1)],[False])
    assert len(g.people)==1
    for _ in range(5):r=g.update([v(0,1)],[True])
    assert r[0]['person']==2
    assert all(len(p)<=6 for p in g.people)
    print('PASS: delayed enrollment, grouped templates, ambiguity, conflict, quality and distinct enrollment')

if __name__=='__main__':main()
