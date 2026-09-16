"""Original calibration input, for upload/GPU tests rather than quality claims."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parent.parent/'demo-assets';root.mkdir(exist_ok=True)
image=Image.new('RGB',(384,256),'#10232f');d=ImageDraw.Draw(image)
for y in range(256):
    d.line((0,y,383,y),fill=(16+int(y*.1),35+int(y*.15),47+int(y*.11)))
for x in range(20,360,12):d.line((x,80,384-x,190),fill='#b6f588',width=1)
d.rectangle((25,20,359,235),outline='#74b8a6',width=2)
d.text((40,38),'COMPUTE RELAY / GPU CALIBRATION',fill='white',font=ImageFont.load_default(size=15))
d.text((40,207),'2x detail test | original team asset',fill='white',font=ImageFont.load_default(size=12))
image.save(root/'calibration.png')
for i in range(1,5):image.resize((768,512)).save(root/f'batch-{i}.png')
print('Created original calibration images in demo-assets/')
