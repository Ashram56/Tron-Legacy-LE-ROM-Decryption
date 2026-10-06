import csv,sys,collections
NAMES={0x02400020:'SOL_A',0x02400021:'SOL_B',0x02400022:'SOL_C',0x02400023:'FLSH',0x02400025:'STATUS',0x02400026:'AUX_DRV',0x02400027:'AUX_IN',0x02400028:'LMP_STB',0x02400029:'AUX_LMP',0x0240002a:'LMP_DRV',0x0240002b:'STRB/GI',0x01100000:'SW_RET',0x01100002:'DED_LO',0x01100004:'DED_HI',0x01100008:'DMDPAGE',0x02580000:'BANK',0x01180000:'XILINX?'}
ENT={0x13624:'TC0_IRQ',0x13688:'TC1_IRQ',0x2b600:'FIQ',0x33300:'IRQ0',0x16a00:'US1',0x16900:'US0',0x12070:'io_tick',0x13440:'lamp_col',0x874:'tube',0x100f0a4:'tubes',0x11fbc:'lampcol_fn',0x1c:'vecFIQ',0x18:'vecIRQ'}
if __name__=="__main__":
    rows=list(csv.DictReader(open(sys.argv[1])))
    cnt=collections.Counter(); 
    for r in rows:
        a=int(r['addr'],16)
        if r['kind']=='ENTRY': cnt['ENTRY '+ENT.get(a,hex(a))]+=1
        else: cnt[r['kind']+' '+NAMES.get(a,hex(a))]+=1
    for k,v in sorted(cnt.items()): print(f"{k:24s}{v}")
