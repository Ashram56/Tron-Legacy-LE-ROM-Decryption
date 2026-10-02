import json,pickle,os,numpy as np,shutil,zipfile,io
from PIL import Image
fr,hs=pickle.load(open('frames.pkl','rb'))
P='/mnt/project-files/tron/mpf_package/media'
lib=json.load(open('animlib.json'))
D=P+'/dmd_library'
if os.path.exists(D): shutil.rmtree(D)
os.makedirs(D)
def img(i):
    a=fr[i]; g=(np.minimum(a,15)*17).astype(np.uint8); al=np.where(a==255,0,255).astype(np.uint8)
    return Image.fromarray(np.dstack([g,g,g,al]),'RGBA') if (a==255).any() else Image.fromarray(g,'L')
for o in lib:
    name=f"anim_{o['anim']:03d}_img{o['first_image']:04d}"; o['name']=name
    d=f'{D}/{name}'; os.makedirs(d+'/frames')
    ims=[]
    for k,i in enumerate(range(o['first_image'],o['last_image']+1)):
        im=img(i); im.save(f'{d}/frames/{k:03d}.png'); ims.append(im.convert('L').convert('P'))
    ims[0].save(f'{d}/animation.gif',save_all=True,append_images=ims[1:],duration=49,loop=0)
json.dump(lib,open(D+'/index.json','w'),indent=1)
# raw dump of every ROM image (fonts, sprites, frames) in one zip
zb=f'{P}/rom_images_all.zip'
with zipfile.ZipFile(zb,'w',zipfile.ZIP_DEFLATED) as z:
    meta=[]
    for i in range(len(hs)):
        b=io.BytesIO(); img(i).save(b,'PNG'); z.writestr(f'{i:04d}.png',b.getvalue())
        h=hs[i]; meta.append({'image':i,'rom_id':h['rid'],'w':h['w'],'h':h['h'],'format':h['type'],'flags':h['flags']})
    z.writestr('index.json',json.dumps(meta))
print('ok')
