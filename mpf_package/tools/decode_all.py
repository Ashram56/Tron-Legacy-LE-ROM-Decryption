from imgdec import *
import pickle
hs=[header(i) for i in range(N)]
r2i={h['rid']:i for i,h in enumerate(hs)}
frames={}
for i in range(N):
    h=hs[i]; prev=None
    if h['type'] in (3,9):
        prev=frames[r2i[h['rid']-1]][1]
    arr,buf=decode(i,prev)
    frames[i]=(arr,bytes(buf))
pickle.dump(({i:frames[i][0] for i in frames},hs),open('frames.pkl','wb'))
print('ok')
