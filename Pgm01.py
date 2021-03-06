import argparse
import os
import tkinter as tk
#from tkinter import messagebox
from tkinter import filedialog
import cv2
#import numpy as np
import threading
#import time
import glob

# import own modules
from ProgramBase import PgmBase
from ThreadBase import ThreadClass
from Utils import Pixels

class VideoInpaint(PgmBase):
    videoObject = None
    videofile = None
    curFrame = None
    curMask = None
    frameIndex = 0
    videoFrames = []    
    maskFrames = []    

    drawRectangle = True
    isSelection = True
    selectionPts = []               # at most 4 points, original user selection points
    circles = []                    # at most 4 circles, keep the drawn ids
    idRectangle = -1

    blending = False
    alpha = 1.0

    isBrushing = False
    isBrushAdd = True
    brushSize = 20
    autoBlending = False

    def __init__(self, root, width=800, height=600, args=[]):
        super().__init__(root, width, height)
        self.title = 'Frame Viewer'
        self.root.title(self.title)
        self.args = args

        # initi thread for video playback
        self.thread = None
        self.threadEventPlayback = threading.Event()

        self.pixels = Pixels()

    def openVideo(self):
        self.videofile = self.args.video
        if self.videofile:
            self.showMessage("Open video : {0:s}".format(self.videofile))
            self.startThread()

    def loadData(self):
        # load data frames
        filename_list = glob.glob(os.path.join(self.args.path, '*.png')) + \
                        glob.glob(os.path.join(self.args.path, '*.jpg'))

        firstFrame = True
        for filename in sorted(filename_list):
            frame = self.loadImage(filename)
            self.videoFrames.append(frame)
            if firstFrame:
                self.curFrame = frame.copy()
                firstFrame = False

        # load mask
        filename_list = glob.glob(os.path.join(self.args.mask, '*.png')) + \
                        glob.glob(os.path.join(self.args.mask, '*.jpg'))

        firstMask = True
        for filename in sorted(filename_list):
            frame_mask = self.loadImage(filename)
            self.maskFrames.append(frame_mask)
            if firstMask:
                self.curMask = frame_mask.copy()
                firstMask = False
                self.drawFrame()  


    ### --- overrite button handlers ---
    def onPrev(self):
        if self.frameIndex > 0 :
            self.frameIndex -= 1
            self.refreshFrame() 
            self.showMessage("Navigate to frame - {0}".format(self.frameIndex))
    
    def onNext(self):
        if self.frameIndex < len(self.videoFrames)-1 :
            self.frameIndex += 1
            self.refreshFrame()  
            self.showMessage("Navigate to frame - {0}".format(self.frameIndex))

    def updateBrushStyle(self):
        self.changeBtnStyle('brush', self.isBrushing)
        self.changeBtnStyle('brush_add', self.isBrushing and self.isBrushAdd)
        self.changeBtnStyle('brush_erase', self.isBrushing and not self.isBrushAdd)
    
    def autoEnableBlending(self):
        # auto enable blending, as brush is used to change mask
        if self.isBrushing and not self.blending:
            self.onBlend()
            self.autoBlending = True

        # undo blending if it is enabled by auto blending
        if not self.isBrushing and self.blending and self.autoBlending:
            self.autoBlending = False
            self.onBlend() 

    def onBrush(self):
        self.isSelection = False
        self.isBrushing = not self.isBrushing
        self.updateBrushStyle()
        
        # update cursor
        style = "circle" if self.isBrushing else "arrow"
        self.changeCursor(style)

        self.autoEnableBlending()

    def onBrushAdd(self):
        self.isBrushAdd = True
        self.updateBrushStyle()
        self.autoEnableBlending()

    def onBrushErase(self):
        self.isBrushAdd = False
        self.updateBrushStyle()
        self.autoEnableBlending()

    def onBlend(self):
        self.autoBlending = False
        self.isSelection = False
        self.blending = not self.blending
        self.changeBtnStyle('blend', self.blending)
        self.drawFrame()  

    def onReset(self):
        # reset selection
        self.showMessage("Selection reset")
        self.selectionPts = []          
        self.destroyDrawObjects()

    def onSave(self):
        if len(self.maskFrames) > 0:
            folderPath = filedialog.askdirectory()
            if len(folderPath) > 0 : # if Esc path = ''
                idx = 0
                for mask in self.maskFrames:
                    frame_file = os.path.join(folderPath, "{:06d}_mask.jpg".format(idx))
                    cv2.imwrite(frame_file, mask)
                    idx += 1
                self.showMessage("Mask saved to folder: {0}".format(folderPath))
            else:
                self.showMessage("Escape saving")

    ### --- event handlers ---
    def onKey(self, event):
        if event.char == event.keysym or len(event.char) == 1:
            if event.keysym in ['Left', 'Right', 'Up', 'Down'] :
                self.onKeyArrors(event.keysym)
            elif event.keysym == 'space':
                self.onSpace()     
            elif event.keysym == 'Escape':
                self.onExit()
        else:
            print (event.keysym)
    
    def onKeyArrors(self, keysym):
        if keysym == 'Left' :
            self.frameIndex = max(self.frameIndex-5, 0)
        elif keysym == 'Right' :
            self.frameIndex = min(self.frameIndex+5, len(self.videoFrames)-1)
        elif keysym == 'Up' :
            self.frameIndex = 0
        elif keysym == 'Down' :
            self.frameIndex = len(self.videoFrames)-1
        self.refreshFrame() 
        self.showMessage("Navigate to frame - {0}".format(self.frameIndex))

    def onSpace(self):
        self.isSelection = False
        self.destroyDrawObjects()

    def onExit(self):
        def _quit():
            self.threadEventPlayback.set()
            self.thread = None
            if self.thread is not None and self.srcVideoObj is not None:
                self.srcVideoObj.release()
                self.srcVideoObj = None
                self.thread = None
            self.root.destroy()

        _quit()

    ### --- thread function ---
    def startThread(self):
        if self.videofile:
            self.threadEventPlayback.set()
            self.thread = ThreadClass(1, "Frame Reading Thread", self, self.readVideoFrame)
            self.threadEventPlayback.clear() 
            self.thread.start()

   
    def readVideoFrame(self):
        def initVideoFrame():
            self.videoObject = cv2.VideoCapture(self.videofile)
            if self.videoObject.isOpened():
                ret, frame = self.videoObject.read()
                if ret:
                    self.curFrame = self.resize(frame)
                    self.videoFrames.append(self.curFrame)
                    self.drawFrame()  # draw current frame
                return ret
            return False

        def readFrame():
            ret, frame = self.videoObject.read()
            if ret:
                self.frameIndex += 1
                frame = self.resize(frame)
                self.videoFrames.append(frame)
            else:
                return False # break
            return True   # continue reading
                    
        ret = initVideoFrame()
        if ret:
            while ret: 
                ret = readFrame()
                if self.threadEventPlayback.wait(0):
                    break
            self.videoObject.release()
            self.threadEventPlayback.clear()

        print('thread stopped, all frames in memery...')
    
    ### --- update frame content---
    def refreshFrame(self):
        self.curFrame = self.videoFrames[self.frameIndex].copy()
        self.curMask = self.maskFrames[self.frameIndex].copy()
        self.drawFrame()

    def drawFrame(self):
        # draw on canvas
        if self.blending:
            if self.mouseLeftDown:
                self.curFrame = self.videoFrames[self.frameIndex].copy()
            beta = ( 1.0 - self.args.alpha )
            cv2.addWeighted( self.curMask, self.args.alpha, self.curFrame, beta, 0.0, self.curFrame)

        self.updateImage(self.curFrame)
        if self.drawRectangle:
            self.drawRect(self.selectionPts)
 
    ### --- canvas drawing funcs ---
    def destroyDrawObjects(self):
        if self.idRectangle:
            self.canvas.delete(self.idRectangle)
            self.idRectangle = -1
        for id in self.circles:  
            self.canvas.delete(id)
        self.circles = []

    def drawRect(self, pts):   
        if len(pts) == 4 and self.isSelection : 
            color = 'red' #if self.isSelection else 'purple'
            dash = (8, 2) #if self.isSelection else (5, 2)
            self.canvas.delete(self.idRectangle)
            self.idRectangle = self.canvas.create_line( int(pts[0][0]+self.imageStartPos[0]), int(pts[0][1]+self.imageStartPos[1]), 
                                                        int(pts[1][0]+self.imageStartPos[0]), int(pts[1][1]+self.imageStartPos[1]),
                                                        int(pts[2][0]+self.imageStartPos[0]), int(pts[2][1]+self.imageStartPos[1]),
                                                        int(pts[3][0]+self.imageStartPos[0]), int(pts[3][1]+self.imageStartPos[1]),
                                                        int(pts[0][0]+self.imageStartPos[0]), int(pts[0][1]+self.imageStartPos[1]),
                                                        fill=color,
                                                        width=2,
                                                        dash=dash)
        else:
            self.destroyDrawObjects()

        # update circles
        for id in self.circles:  
            self.canvas.delete(id)
        if self.isSelection:
            self.circles = []
            for p in pts:
                id = self.create_circle(p[0]+self.imageStartPos[0], p[1]+self.imageStartPos[1], 2, self.canvas)
                self.circles.append(id)
    
    # (x,y): center, r: radius
    def create_circle(self, x, y, r, canvas): 
        x0, y0 = x-r, y-r
        x1, y1 = x+r, y+r
        return canvas.create_oval(x0, y0, x1, y1, fill="orange", outline='orange', width=3)

    # selection to add control points
    def updateCloudPoints(self, mousePt):
        def _replaceNearestSelectionPt(mousePt):
            mindist = 1000000
            indexMin = index = 0
            for pt in self.selectionPts:
                dist = self.pixels.norm2Distance(mousePt, pt)
                if dist < mindist:
                    mindist = dist
                    indexMin = index
                index += 1
            self.selectionPts[indexMin] = mousePt

        if len(self.selectionPts) < 4:
            self.selectionPts.append(mousePt)
        else:
            _replaceNearestSelectionPt(mousePt)
        
        if self.drawRectangle:
            self.drawRect(self.selectionPts)

    def mouseLClick(self, event):
        if self.isSelection:
            if self.hitTestImageRect(event, self.imageClickPos):
                print('({}, {})'.format(self.imageClickPos[0], self.imageClickPos[1]))
                self.updateCloudPoints(self.imageClickPos)

    def mouseLRelease(self, event):
        super().mouseLRelease(event) 
        self.maskFrames[self.frameIndex] = self.curMask.copy()
        self.refreshFrame()

    def mouseMove(self, event):
        super().mouseMove(event) 
        if not self.isSelection and self.isBrushing and self.mouseLeftDown:
            #print('painting', self.imgPosX, self.imgPosY)
            color = (64, 128, 64)
            cv2.circle(self.curFrame, (self.imgPosX, self.imgPosY), self.brushSize, color, -1)
            maskColor = (255, 255, 255) if self.isBrushAdd else  (0, 0, 0)
            cv2.circle(self.curMask, (self.imgPosX, self.imgPosY), self.brushSize, maskColor, -1)
            self.drawFrame()
    
    def mouseWheel(self, event):
        if self.isBrushing:
            self.brushSize += event.delta
            self.brushSize = max(self.brushSize, 3)
            self.showMessage("Brush size = {0:03d}".format(self.brushSize))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', default='data/tennis', help="input data folder")
    parser.add_argument('--mask', default='data/tennis_mask', help="input data mask folder")
    parser.add_argument('--video', default='data/cheetah.mp4', help="input video")
    parser.add_argument('--alpha', default=0.2, help="alpha blending") 

    # RAFT model arguments
    '''
    parser.add_argument('--model', default='RAFT/models/raft-things.pth', help="restore checkpoint")
    parser.add_argument('--small', action='store_true', help='use small model')
    parser.add_argument('--mixed_precision', action='store_true', help='use mixed precision')
    parser.add_argument('--alternate_corr', action='store_true', help='use efficent correlation implementation')
    '''
    args = parser.parse_args()

    # process first file to get shape
    filename_list = glob.glob(os.path.join(args.path, '*.png')) + \
                    glob.glob(os.path.join(args.path, '*.jpg'))
    
    if len(filename_list) > 0:
        img = cv2.imread(filename_list[0])
        height, width = img.shape[0], img.shape[1]
        img = None
        program = VideoInpaint(tk.Tk(), width, height, args)
        program.loadData()
    else:   # process video
        program = VideoInpaint(tk.Tk(), 1280, 720, args)
        program.openVideo()
    
    program.run()
