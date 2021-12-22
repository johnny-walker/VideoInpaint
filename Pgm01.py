import argparse
import os
import tkinter as tk
#from tkinter import messagebox
from tkinter import filedialog
import cv2
#import numpy as np
import threading
#import time

# import own modules
from ProgramBase import PgmBase
from ThreadBase import ThreadClass
from PixelUtil import Pixels

class VideoInpaint(PgmBase):
    videoObject = None
    videofile = None
    curFrame = None
    frameIndex = 0
    videoFrames = []    

    drawRectangle = True
    isSelection = True
    selectionPts = []               # at most 4 points, original user selection points
    circles = []                    # at most 4 circles, keep the drawn ids
    idRectangle = -1
    drawing = False

    alpha = 1.0
    debugPoints = None
    
    def __init__(self, root, width=800, height=600):
        super().__init__(root, width, height)
        self.title = 'Frame Viewer'
        self.root.title(self.title)

        # initi thread for video playback
        self.thread = None
        self.threadEventPlayback = threading.Event()

        self.pixels = Pixels()

    ### --- overrite button handlers ---
    def onOpen(self):
        None

    def onReset(self):
        self.threadEventPlayback.clear()
        self.showMessage("reset")
        self.selectionPts = []          
        if self.idRectangle:
            self.canvas.delete(self.idRectangle)
            self.idRectangle = -1 
        if len(self.circles) > 0:
            for id in self.circles:  
                self.canvas.delete(id)
            self.circles = []


    ### --- event handlers ---
    def onKey(self, event):
        if event.char == event.keysym or len(event.char) == 1:
            if event.keysym == 'k':
                self.onK()
            elif event.keysym == 'r':
                self.onR()
            elif event.keysym == 'h':
                self.onH()
            elif event.keysym == 's' or event.keysym == 'p':
                self.onPlay()
            elif event.keysym == 'space':
                self.onSpace()     
            elif event.keysym == 'Escape':
                self.onExit()
    
    def onK(self):
        None
    
    def onR(self):
        None
    
    def onH(self):
        None  
    
    def onSpace(self):
        self.isSelection = False

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

    def openVideo(self, path):
        self.videofile = path
        if self.videofile:
            self.showMessage("playback video file: {0:s}".format(self.videofile))
            self.startThread()


    ### --- thread function ---
    def startThread(self):
        if self.videofile:
            self.threadEventPlayback.set()
            self.thread = ThreadClass(1, "Frame Reading Thread", self, self.readVideoFrame)
            self.threadEventPlayback.clear() 
            self.thread.start()

    def initVideoFrame(self):
        self.videoObject = cv2.VideoCapture(self.videofile)
        if self.videoObject.isOpened():
            ret, frame = self.videoObject.read()
            if ret:
                self.curFrame = self.resize(frame)
                self.videoFrames.append(self.curFrame)
                self.drawFrame()  # draw current frame
            return ret
        return False
    
    def readVideoFrame(self):
        def readFrame():
            ret, frame = self.videoObject.read()
            if ret:
                self.frameIndex += 1
                frame = self.resize(frame)
                self.videoFrames.append(frame)
            else:
                return False # break
            return True   # continue reading
                    
        ret = self.initVideoFrame()
        if ret:
            while ret: 
                ret = readFrame()
                if self.threadEventPlayback.wait(0):
                    break
            self.videoObject.release()
            self.threadEventPlayback.clear()

        print('thread stopped, all frames in memery...')
    
    ### --- update frame content---
    def drawFrame(self):
        # draw on canvas
        self.updateImage(self.curFrame)
        if self.drawRectangle:
            self.drawRect(self.selectionPts)
 
    # (mouse selection) add control points
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

    ### --- canvas drawing funcs ---
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
            # destroy drawing objects
            if self.idRectangle:
                self.canvas.delete(self.idRectangle)
                self.idRectangle = -1
        
        # update circles
        for id in self.circles:  
            self.canvas.delete(id)
        if self.isSelection:
            self.circles = []
            for p in pts:
                id = self.create_circle(p[0]+self.imageStartPos[0], p[1]+self.imageStartPos[1], 2, self.canvas)
                self.circles.append(id)
    
    # params: center coordinates, radius
    def create_circle(self, x, y, r, canvas): 
        x0, y0 = x-r, y-r
        x1, y1 = x+r, y+r
        return canvas.create_oval(x0, y0, x1, y1, fill="orange", outline='orange', width=3)

    def mouseLClick(self, event):
        if self.isSelection:
            if self.hitTestImageRect(self.imageClickPos):
                print('({}, {})'.format(self.imageClickPos[0], self.imageClickPos[1]))
                self.updateCloudPoints(self.imageClickPos)

    def mouseMove(self, event):
        super().mouseMove(event) 
        if not self.isSelection and self.mouseLDown:
            print('painting', self.imgPosX, self.imgPosY)
            cv2.circle(self.curFrame, (self.imgPosX, self.imgPosY), 10, (0,0,255), -1)
            self.drawFrame()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='data/cheetah', help="input folder")
    parser.add_argument('--video', default='data/cheetah.mp4', help="input video")
    parser.add_argument('--alpha', default=0.6, help="alpha blending") 

    # RAFT model arguments
    '''
    parser.add_argument('--model', default='RAFT/models/raft-things.pth', help="restore checkpoint")
    parser.add_argument('--small', action='store_true', help='use small model')
    parser.add_argument('--mixed_precision', action='store_true', help='use mixed precision')
    parser.add_argument('--alternate_corr', action='store_true', help='use efficent correlation implementation')
    '''
    args = parser.parse_args()

    program = VideoInpaint(tk.Tk(), 1280, 720)
    program.openVideo(args.video)
    program.run()
