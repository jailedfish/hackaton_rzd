import os
from asyncio import timeout

from aiohttp import web
import cv2
import pydantic
from threading import Thread
from aiohttp.web_request import FileField

router = web.RouteTableDef()

def clear_cycle(interval: int):
    import time
    while True:
        list_res = os.listdir('./tmp/')
        for entry in list_res:
            if 'processed_' + entry in list_res:
                os.remove('./tmp/' + entry)


        time.sleep(interval)

Thread(target=clear_cycle, args=(25,)).start()

def get_road_marks(frame, drawto):
  f = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
  retval, thresh = cv2.threshold(f, 215, 255, cv2.THRESH_BINARY)
  contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE , cv2.CHAIN_APPROX_NONE)
  larges = [cnt for cnt in contours if cv2.contourArea(cnt) < 1250]
  subf = drawto
  cv2.drawContours(subf, larges, -1, (0,255,0), 1, cv2.LINE_4, hierarchy, 1 )

def process(frame, backSub, frameid):
    fg_mask = backSub.apply(frame)
    contours_c, hierarchy_c = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if frameid > 5:
        get_road_marks(backSub.getBackgroundImage(), frame)

    retval, mask_thresh = cv2.threshold( fg_mask, 180, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    # Apply erosion
    mask_eroded = cv2.morphologyEx(mask_thresh, cv2.MORPH_OPEN, kernel)

    large_contours = [cnt for cnt in contours_c if cv2.contourArea(cnt) > 500]
    frame_out = frame
    for cnt in large_contours:
      x, y, w, h = cv2.boundingRect(cnt)
      frame_out = cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)

    # отображаем результат
    return frame_out


def process_video(vid_fname: str) -> str:
    print(vid_fname)
    if f"./tmp/processed_{vid_fname}" in os.listdir():
        return f"./tmp/processed_{vid_fname}"
    if f"./tmp/processing_{vid_fname}" in os.listdir():
        return  "already_processing"
    cap = cv2.VideoCapture(f"./tmp/{vid_fname}")
    cap.set(cv2.CAP_PROP_FPS, 10)
    output = cv2.VideoWriter(f"./tmp/processing_{vid_fname}", cv2.VideoWriter_fourcc(*'MPEG'), 30, (800, 600))
    backSub = cv2.createBackgroundSubtractorMOG2()
    if not cap.isOpened():
        print("Error opening video file")

    rets = 0
    frameid = 0
    while cap.isOpened():
        # Захват кадр за кадром
        ret, frame = cap.read()

        if ret:
            rets = 0
            frameid += 1
            output.write(process(frame, backSub, frameid))

        else:
            if rets > 10:
                break
            rets += 1
    output.release()
    os.rename(f"./tmp/processing_{vid_fname}", f"./tmp/processed_{vid_fname}")
    return f"./tmp/processed_{vid_fname}"
@router.get('/')
async def root_handler(r: web.Request):
    return web.Response(body=open('html/index.html', 'r').read(), status=200, content_type='text/html')

@router.get('/static/{path}/{subpath}')
async def static_handler(r: web.Request):
    path, subpath = r.match_info.values()
    if path not in ['tmp', 'js', 'css']:
        return web.Response(status=403)
    try:
        return web.Response(body=open(f'./{path}/{subpath}'))
    except:
        return web.Response(status=404)


@router.post('/upload')
async def upload_handler(r: web.Request):
    data = await r.post()
    if not isinstance(data.get('input'), FileField):
        print('fuzz')
        return web.Response(status=400)

    if not data['input'].content_type.startswith('video/'):
        print('buzz')
        return web.Response(status=400)
    open(f'tmp/{data.get('input').filename}', 'wb').write(data.get('input').file.read())
    try:
        Thread(target=process_video, args=(data.get('input').filename,)).start()
    except FileExistsError:
        return web.Response(status=409)
    except:
        return web.Response(status=500)
    else:

        return web.json_response(data={'out_path': f"/tmp/processed_{data.get('input').filename}"}, status=200)


app = web.Application(client_max_size=3*(10**10), handler_args={"timeout_ceil_threshold": 60*15})
app.add_routes(router)
web.run_app(app, host='localhost', port=3000)