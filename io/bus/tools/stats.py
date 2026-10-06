import csv,sys,statistics as st
def ticks(fn):
    rows=list(csv.DictReader(open(fn)))
    idx=[i for i,r in enumerate(rows) if r['kind']=='ENTRY' and int(r['addr'],16)==0x13624]
    out=[]
    for k in range(len(idx)-1):
        seg=rows[idx[k]:idx[k+1]]; c0=int(seg[0]['cycles'])
        ws=[r for r in seg if r['kind'] in('W','R') and int(r['addr'],16)>>16 in (0x240,0x110)]
        out.append((c0,seg,ws))
    return rows,out
for fn in sys.argv[1:]:
    rows,T=ticks(fn)
    per=[T[i+1][0]-T[i][0] for i in range(len(T)-1)]
    last=[(int(ws[-1]['cycles'])-c0)*0.025 for c0,seg,ws in T if ws]
    blank2col=[];sp=[]
    for i,r in enumerate(rows):
        if r['kind']=='W' and int(r['addr'],16)==0x0240002a and r['pc']=='0x132f0':
            c=int(r['cycles'])
            for r2 in rows[i:i+400]:
                if r2['kind']=='W' and r2['pc']=='0x11fe4': blank2col.append((int(r2['cycles'])-c)*0.025); break
        if r['kind']=='W' and r['pc']=='0x133cc' and int(r['addr'],16)==0x02400021:
            sp.append([(int(x['cycles'])-int(r['cycles']))*0.025 for x in rows[i:i+8] if x['kind']=='W'][:7])
    print(fn, 'ticks',len(T),'period us min/med/max', min(per)*0.025, st.median(per)*0.025, max(per)*0.025)
    print('  last IO access in tick (us) min/med/max', min(last), st.median(last), max(last))
    if blank2col: print('  lamp blank->column write us min/med/max', min(blank2col), st.median(blank2col), max(blank2col))
    if sp: print('  coil burst offsets us (SOL_B,SOL_A,SOL_C,FLSH,AUX,STB lo,STB hi):', sp[0])
