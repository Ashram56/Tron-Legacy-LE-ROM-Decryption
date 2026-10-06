import csv,sys
def load(p):
    rows=list(csv.reader(open(p)))
    hdr=rows[0]; data=[list(map(int,r)) for r in rows[1:]]
    return hdr,data
hdr,data=load(sys.argv[1])
# events: IOSTB low runs
ev=[];i=0;n=len(data)
while i<n:
    if data[i][9]==0:
        j=i
        while j<n and data[j][9]==0: j+=1
        r=data[i]; d=sum(r[k]<<k for k in range(8)); a=r[10]|r[11]<<1|r[12]<<2|r[13]<<3
        # check stable
        dvals=set(sum(data[k][b]<<b for b in range(8)) for k in range(i,j))
        avals=set(data[k][10]|data[k][11]<<1|data[k][12]<<2|data[k][13]<<3 for k in range(i,j))
        ev.append((i,j-i,a,d,dvals,avals))
        i=j
    else: i+=1
print(len(ev),'strobes')
for e in ev[:400]: print(e[0],e[1],hex(e[2]),hex(e[3]), e[4] if len(e[4])>1 else '', e[5] if len(e[5])>1 else '')
