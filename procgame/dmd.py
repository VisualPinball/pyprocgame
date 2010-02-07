import pinproc
import struct
import time
import os

class Frame(pinproc.DMDBuffer):
	"""DMD frame/bitmap."""
	def __init__(self, width, height):
		super(Frame, self).__init__(width, height)
		self.width = width
		self.height = height

	def copy_rect(dst, dst_x, dst_y, src, src_x, src_y, width, height, op="copy"):
		if not (issubclass(type(dst), pinproc.DMDBuffer) and issubclass(type(src), pinproc.DMDBuffer)):
			raise ValueError, "Incorrect types"
		src.copy_to_rect(dst, dst_x, dst_y, src_x, src_y, width, height, op)
	copy_rect = staticmethod(copy_rect)

class Animation(object):
	"""A set of frames."""
	def __init__(self):
		super(Animation, self).__init__()
		self.width = None
		self.height = None
		self.frames = []
	def load(self, filename):
		"""Loads a series of frames from a .dmd (DMDAnimator) file.
		
		File format is as follows:
		
		  4 bytes - header data (unused)
		  4 bytes - frame_count
		  4 bytes - width of animation frames in pixels
		  4 bytes - height of animation frames in pixels
		  ? bytes - Frames: frame_count * width * height bytes
		
		Frame data is laid out row0..rowN.  Byte values of each pixel
		are 00-03, 00 being black and 03 being brightest.  This is
		subject to change to allow for more brightness levels and/or
		transparency.
		"""
		self.frames = []
		f = open(filename, 'rb')
		f.seek(4)
		frame_count = struct.unpack("I", f.read(4))[0]
		self.width = struct.unpack("I", f.read(4))[0]
		self.height = struct.unpack("I", f.read(4))[0]
		if os.path.getsize(filename) != 16 + self.width * self.height * frame_count:
			raise ValueError, "File size inconsistent with header information.  Old or incompatible file format?"
		for frame_index in range(frame_count):
			str_frame = f.read(self.width * self.height)
			new_frame = Frame(self.width, self.height)
			new_frame.set_data(str_frame)
			self.frames += [new_frame]
		return self

	def save(self, filename):
		if self.width == None or self.height == None:
			raise ValueError, "width and height must be set on Animation before it can be saved."
		header = struct.pack("IIII", 0x00646D64, len(self.frames), self.width, self.height)
		if len(header) != 16:
			raise ValueError, "Packed size not 16 bytes as expected: %d" % (len(header))
		f = open(filename, 'w')
		f.write(header)
		for frame in self.frames:
			f.write(frame.get_data())
		f.close()

class Font(object):
	"""A DMD bitmap font."""
	def __init__(self, filename=None):
		super(Font, self).__init__()
		self.__anim = Animation()
		self.char_size = None
		self.bitmap = None
		self.char_widths = None
		if filename != None:
			self.load(filename)
		
	def load(self, filename):
		"""Loads the font from a .dmd file (see Animation.load()).
		Fonts are stored in .dmd files with frame 0 containing the bitmap data
		and frame 1 containing the character widths.  96 characters (32..127,
		ASCII printables) are stored in a 10x10 grid, starting with space ' ' 
		in the upper left.
		"""
		self.__anim.load(filename)
		if self.__anim.width != self.__anim.height:
			raise ValueError, "Width != height!"
		if len(self.__anim.frames) == 1:
			# We allow 1 frame for handmade fonts.
			# This is so that they can be loaded as a basic bitmap, have their char widths modified, and then be saved.
			print "Font animation file %s has 1 frame; adding one" % (filename)
			self.__anim.frames += [Frame(self.__anim.width, self.__anim.height)]
		elif len(self.__anim.frames) != 2:
			raise ValueError, "Expected 2 frames: %d" % (len(self.__anim.frames))
		self.char_size = self.__anim.width / 10
		self.bitmap = self.__anim.frames[0]
		self.char_widths = []
		for i in range(96):
			self.char_widths += [self.__anim.frames[1].get_dot(i%self.__anim.width, i/self.__anim.width)]
	
	def save(self, filename):
		"""Save the font to the given path."""
		out = Animation()
		out.width = self.__anim.width
		out.height = self.__anim.height
		out.frames = [self.bitmap, Frame(out.width, out.height)]
		for i in range(96):
			out.frames[1].set_dot(i%self.__anim.width, i/self.__anim.width, self.char_widths[i])
		out.save(filename)
		
	def draw(self, frame, text, x, y):
		"""Uses this font's characters to draw the given string at the given position."""
		for ch in text:
			char_offset = ord(ch) - ord(' ')
			if char_offset < 0 or char_offset >= 96:
				continue
			char_x = self.char_size * (char_offset % 10)
			char_y = self.char_size * (char_offset / 10)
			width = self.char_widths[char_offset]
			Frame.copy_rect(dst=frame, dst_x=x, dst_y=y, src=self.bitmap, src_x=char_x, src_y=char_y, width=width, height=self.char_size)
			x += width
		return x
	
	def size(self, text):
		"""Returns a tuple of the width and height of this text as rendered with this font."""
		x = 0
		for ch in text:
			char_offset = ord(ch) - ord(' ')
			if char_offset < 0 or char_offset >= 96:
				continue
			width = self.char_widths[char_offset]
			x += width
		return (x, self.char_size)


class Layer(object):
	"""Abstract layer object."""
	def __init__(self, opaque=False):
		super(Layer, self).__init__()
		self.opaque = opaque
		self.set_target_position(0, 0)
		self.target_x_offset = 0
		self.target_y_offset = 0
		self.enabled = True
		self.composite_op = 'copy'
	def set_target_position(self, x, y):
		"""Sets the location in the final output that this layer will be positioned at."""
		self.target_x = x
		self.target_y = y
	def next_frame(self):
		"""Returns the frame to be shown, or None if there is no frame."""
		return None
	def composite_next(self, target):
		"""Composites the next frame of this layer onto the given target buffer."""
		src = self.next_frame()
		if src != None:
			Frame.copy_rect(dst=target, dst_x=self.target_x+self.target_x_offset, dst_y=self.target_y+self.target_y_offset, src=src, src_x=0, src_y=0, width=src.width, height=src.height, op=self.composite_op)
		return src

class FrameLayer(Layer):
	def __init__(self, opaque=False, frame=None):
		super(FrameLayer, self).__init__(opaque)
		self.frame = frame
	def next_frame(self):
		return self.frame

class AnimatedLayer(Layer):
	"""Collection of frames displayed sequentially, as an animation.  Optionally holds the last frame on-screen."""
	def __init__(self, opaque=False, hold=True, repeat=False, frame_time=1, frames=None):
		super(AnimatedLayer, self).__init__(opaque)
		self.hold = hold
		self.repeat = repeat
		if frames == None:
			self.frames = list()
		else:
			self.frames = frames
		self.frame_time = frame_time # Number of frames each frame should be displayed for before moving to the next.
		self.frame_time_counter = self.frame_time
	def next_frame(self):
		"""Returns the frame to be shown, or None if there is no frame."""
		if len(self.frames) == 0:
			return None
		frame = self.frames[0] # Get the first frame in this layer's list.
		self.frame_time_counter -= 1
		if (self.hold == False or len(self.frames) > 1) and (self.frame_time_counter == 0):
			if self.repeat:
				f = self.frames[0]
				del self.frames[0]
				self.frames += [f]
			else:
				del self.frames[0] # Pop off the frame if there are others
		if self.frame_time_counter == 0:
			self.frame_time_counter = self.frame_time
		return frame

class TextLayer(Layer):
	"""Layer that displays text."""
	def __init__(self, x, y, font, justify="left", opaque=False):
		super(TextLayer, self).__init__(opaque)
		self.set_target_position(x, y)
		self.font = font
		self.started_at = None
		self.seconds = None # Number of seconds to show the text for
		self.frame = None # Frame that text is rendered into.
		self.justify = justify
		
	def set_text(self, text, seconds=None):
		"""Displays the given message for the given number of seconds."""
		self.started_at = None
		self.seconds = seconds
		if text == None:
			self.frame = None
		else:
			(w, h) = self.font.size(text)
			self.frame = Frame(w, h)
			self.font.draw(self.frame, text, 0, 0)
			if self.justify == "left":
				(self.target_x_offset, self.target_y_offset) = (0,0)
			elif self.justify == "right":
				(self.target_x_offset, self.target_y_offset) = (-w,0)
			elif self.justify == "center":
				(self.target_x_offset, self.target_y_offset) = (-w/2,0)
		return self

	def next_frame(self):
		if self.started_at == None:
			self.started_at = time.time()
		if (self.seconds != None) and ((self.started_at + self.seconds) < time.time()):
			self.frame = None
		return self.frame
	
	def is_visible(self):
		return self.frame != None

class ScriptedLayer(Layer):
	"""Displays a set of layers based on a simple script (dictionary)."""
	def __init__(self, width, height, script):
		super(ScriptedLayer, self).__init__()
		self.buffer = Frame(width, height)
		self.script = script
		self.script_index = 0
		self.frame_start_time = None
	
	def next_frame(self):
		# This assumes looping.  TODO: Add code to not loop!
		if self.frame_start_time == None:
			self.frame_start_time = time.time()
		script_item = self.script[self.script_index]
		time_on_frame = time.time() - self.frame_start_time
		if time_on_frame > script_item['seconds']:
			# Time for the next frame:
			self.script_index += 1
			if self.script_index == len(self.script):
				self.script_index = 0
			script_item = self.script[self.script_index]
			self.frame_start_time = time.time()
		layer = script_item['layer']
		if layer != None:
			self.buffer.clear()
			layer.composite_next(self.buffer)
			return self.buffer
		else:
			return None
			

class GroupedLayer(Layer):
	"""docstring for GroupedLayer"""
	def __init__(self, width, height, layers=None):
		super(GroupedLayer, self).__init__()
		self.buffer = Frame(width, height)
		if layers == None:
			self.layers = list()
		else:
			self.layers = layers

	def next_frame(self):
		self.buffer.clear()
		composited_count = 0
		for layer in self.layers:
			frame = None
			if layer.enabled:
				frame = layer.composite_next(self.buffer)
			if frame != None:
				composited_count += 1
			if frame != None and layer.opaque: # If an opaque layer doesn't draw anything, don't stop.
				break
		if composited_count == 0:
			return None
		return self.buffer

class DisplayController:
	"""DisplayController, on update(), iterates over the game's mode and composites their layer member variable to the output."""
	def __init__(self, game, width=128, height=32, message_font=None):
		self.game = game
		self.message_layer = None
		self.width = width
		self.height = height
		if message_font != None:
			self.message_layer = TextLayer(width/2, height-2*7, message_font, "center")
		# Do two updates to get the pump primed:
		for x in range(2):
			self.update()
		
	def set_message(self, message, seconds):
		if self.message_layer == None:
			raise ValueError, "Message_font must be specified in constructor to enable message layer."
		self.message_layer.set_text(message, seconds)

	def update(self):
		"""Update the DMD."""
		layers = []
		for mode in self.game.modes.modes:
			if hasattr(mode, 'layer') and mode.layer != None:
				layers += [mode.layer]
		
		frame = Frame(self.width, self.height)
		for layer in layers[::-1]: # We reverse the list here so that the top layer gets the last say.
			if layer.enabled:
				layer.composite_next(frame)
		
		if self.message_layer != None:
			self.message_layer.composite_next(frame)
			
		if frame != None:
			self.game.proc.dmd_draw(frame)

