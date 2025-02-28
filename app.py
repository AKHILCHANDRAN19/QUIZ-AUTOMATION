#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-question Quiz Video Generator with Blue Template

This script prompts you to select a video ratio:
  Enter 1 for 16:9 (default) or 2 for 9:16 (vertical).
Then, you are asked to enter your quiz questions interactively in the following format:

Example:
1. What is the capital of France?
a) Paris
b) Berlin
c) London
d) Madrid
Answer: d) Madrid

Enter an empty line between questions and type "DONE" on a new line when finished.

For each question, a 13-second clip is created on a blue background with white text:
  - The question displayed in a box below the timer
  - The four options displayed in separate rounded boxes below
  - Text wraps to the next line for long sentences rather than reducing font size
  - Question font is always larger than option font
  - Correct answer blinks green from 10 to 13 seconds
A timer video (timer.mp4) is processed (green screen removed, audio preserved) and placed at the top center.
Each clip is saved into the "OUTPUT" folder and concatenated into a final video.
"""

import cv2
import numpy as np
import sys
from PIL import Image, ImageDraw, ImageFont
from moviepy.video.VideoClip import ImageClip, VideoClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from dataclasses import dataclass
from moviepy.Clip import Clip
from moviepy.Effect import Effect

# Default video dimensions (16:9) and flag for vertical layout
video_width = 1280
video_height = 720
vertical_layout = False

### Global File Paths ###
base_path = "/storage/emulated/0/Download/"
timer_video_path = base_path + "timer.mp4"
font_path = base_path + "BebasNeue-Regular.ttf"

### FadeIn Effect ###
@dataclass
class FadeIn(Effect):
    duration: float
    initial_color: list = None

    def apply(self, clip: Clip) -> Clip:
        if self.initial_color is None:
            self.initial_color = 0 if clip.is_mask else [0, 0, 0]
        self.initial_color = np.array(self.initial_color)
        def filter(get_frame, t):
            if t >= self.duration:
                return get_frame(t)
            else:
                fading = t / self.duration
                return fading * get_frame(t) + (1 - fading) * self.initial_color
        return clip.transform(filter)

### Helper Functions ###

def break_word(word, font, max_width):
    """Breaks a single word into segments that fit within max_width."""
    segments = []
    current_segment = ""
    for char in word:
        test_segment = current_segment + char
        width = font.getbbox(test_segment)[2] - font.getbbox(test_segment)[0]
        if width <= max_width:
            current_segment = test_segment
        else:
            if current_segment:
                segments.append(current_segment)
            current_segment = char
    if current_segment:
        segments.append(current_segment)
    return segments

def draw_centered_wrapped_text(draw_obj, region, text, font, text_color):
    """
    Draws centered wrapped text within a given region.
    Splits the text into lines that fit within region width.
    If a word is too long, it is broken into segments.
    The block of text is then vertically centered within the region.
    """
    x1, y1, x2, y2 = region
    max_width = x2 - x1
    words = []
    for word in text.split():
        # If the word itself is too long, break it into segments.
        word_width = font.getbbox(word)[2] - font.getbbox(word)[0]
        if word_width > max_width:
            segments = break_word(word, font, max_width)
            words.extend(segments)
        else:
            words.append(word)
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        test_line_width = font.getbbox(test_line)[2] - font.getbbox(test_line)[0]
        if test_line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    # Determine line height using a sample string
    line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
    spacing = 5  # pixels between lines
    total_height = len(lines) * line_height + (len(lines) - 1) * spacing
    start_y = y1 + ((y2 - y1) - total_height) // 2
    for line in lines:
        # Calculate horizontal position for centered text
        line_width = font.getbbox(line)[2] - font.getbbox(line)[0]
        x_centered = x1 + (max_width - line_width) // 2
        draw_obj.text((x_centered, start_y), line, font=font, fill=text_color)
        start_y += line_height + spacing

def draw_rounded_rectangle(draw, xy, radius, fill=None, outline=None, width=1):
    """Draw a rounded rectangle"""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)

def adjust_font_size(text, font_path, max_size, region_width, region_height):
    font_size = max_size
    while font_size > 5:
        font = ImageFont.truetype(font_path, font_size)
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= region_width and text_h <= region_height:
            return font
        font_size -= 1
    return ImageFont.truetype(font_path, font_size)

def concatenate_videoclips(clips):
    start = 0
    new_clips = []
    for clip in clips:
        new_clips.append(clip.with_start(start))
        start += clip.duration
    return CompositeVideoClip(new_clips, size=clips[0].size).with_duration(start)

### Interactive Quiz Input Functions ###
def get_quiz_input():
    print("Enter your quiz questions in the following format:")
    print("Example:")
    print("1. What is the capital of France?")
    print("a) Paris")
    print("b) Berlin")
    print("c) London")
    print("d) Madrid")
    print("Answer: d) Madrid")
    print("Enter an empty line between questions. When finished, type 'DONE' on a new line.")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "DONE":
            break
        lines.append(line)
    return "\n".join(lines)

def parse_quiz_text(text):
    """
    Parses the interactive quiz input.
    Preserves the question number, option markers, and answer markers.
    """
    questions = []
    blocks = []
    current_block = []
    for line in text.splitlines():
        line = line.strip()
        if line == "":
            if current_block:
                blocks.append(current_block)
                current_block = []
        else:
            current_block.append(line)
    if current_block:
        blocks.append(current_block)
    for block in blocks:
        if len(block) < 6:
            continue
        question = block[0]
        opt_a = block[1]
        opt_b = block[2]
        opt_c = block[3]
        opt_d = block[4]
        answer_line = block[5]
        if answer_line.lower().startswith("answer:"):
            answer = answer_line[len("answer:"):].strip()
        else:
            answer = answer_line.strip()
        questions.append({
            "question": question,
            "opt_a": opt_a,
            "opt_b": opt_b,
            "opt_c": opt_c,
            "opt_d": opt_d,
            "answer": answer
        })
    return questions

### Function to Create a Quiz Clip with Blue Template and Blinking Green Answer ###
def make_quiz_clip(question_text, opt_a_text, opt_b_text, opt_c_text, opt_d_text, answer_text):
    # Create a blue background image - using a deep blue color as in the provided template
    blue_bg_color = (27, 42, 144)  # Deep blue color
    bg_img = Image.new("RGB", (video_width, video_height), blue_bg_color)
    draw = ImageDraw.Draw(bg_img)
    
    # Set colors
    text_color = (255, 255, 255)  # White for text
    box_outline_color = (255, 255, 255)  # White for box outlines
    
    # Process timer video to get its dimensions
    try:
        timer_clip = VideoFileClip(timer_video_path).with_duration(11.56)
        timer_height = 100  # Desired height for timer
        orig_timer_width, orig_timer_height = timer_clip.size
        scale_factor = timer_height / orig_timer_height
        timer_width = int(orig_timer_width * scale_factor)
    except Exception as e:
        sys.exit("Error loading timer video: " + str(e))
    
    # Define timer position - centered at top with padding
    timer_top_padding = 20
    timer_position = ((video_width - timer_width) // 2, timer_top_padding)
    
    # Define box and text regions based on aspect ratio - now positioned BELOW the timer
    if not vertical_layout:
        # 16:9 layout
        margin = 50
        box_radius = 20
        
        # Question box - positioned below the timer
        q_box_top = timer_top_padding + timer_height + 20  # 20px gap after timer
        q_box_height = 120
        q_box_region = (margin, q_box_top, video_width - margin, q_box_top + q_box_height)
        
        # Option boxes - arranged in 2x2 grid
        opt_width = (video_width - (3 * margin)) // 2
        opt_height = 60
        opt_top_row_y = q_box_top + q_box_height + 30
        opt_bottom_row_y = opt_top_row_y + opt_height + 30
        
        opt_a_box = (margin, opt_top_row_y, margin + opt_width, opt_top_row_y + opt_height)
        opt_b_box = (video_width - margin - opt_width, opt_top_row_y, video_width - margin, opt_top_row_y + opt_height)
        opt_c_box = (margin, opt_bottom_row_y, margin + opt_width, opt_bottom_row_y + opt_height)
        opt_d_box = (video_width - margin - opt_width, opt_bottom_row_y, video_width - margin, opt_bottom_row_y + opt_height)
    else:
        # 9:16 vertical layout
        margin = 40
        box_radius = 20
        
        # Question box - positioned below the timer
        q_box_top = timer_top_padding + timer_height + 20  # 20px gap after timer
        q_box_height = 150
        q_box_region = (margin, q_box_top, video_width - margin, q_box_top + q_box_height)
        
        # Option boxes - stacked vertically
        opt_width = video_width - (2 * margin)
        opt_height = 60
        opt_spacing = 25  # Reduced spacing to fit all on screen
        
        opt_a_box = (margin, q_box_top + q_box_height + 30, video_width - margin, q_box_top + q_box_height + 30 + opt_height)
        opt_b_box = (margin, opt_a_box[3] + opt_spacing, video_width - margin, opt_a_box[3] + opt_spacing + opt_height)
        opt_c_box = (margin, opt_b_box[3] + opt_spacing, video_width - margin, opt_b_box[3] + opt_spacing + opt_height)
        opt_d_box = (margin, opt_c_box[3] + opt_spacing, video_width - margin, opt_c_box[3] + opt_spacing + opt_height)
    
    # Draw rounded rectangles for question and options
    draw_rounded_rectangle(draw, q_box_region, radius=box_radius, outline=box_outline_color, width=2)
    draw_rounded_rectangle(draw, opt_a_box, radius=box_radius, outline=box_outline_color, width=2)
    draw_rounded_rectangle(draw, opt_b_box, radius=box_radius, outline=box_outline_color, width=2)
    draw_rounded_rectangle(draw, opt_c_box, radius=box_radius, outline=box_outline_color, width=2)
    draw_rounded_rectangle(draw, opt_d_box, radius=box_radius, outline=box_outline_color, width=2)
    
    # Add option labels (A:, B:, C:, D:)
    label_margin = 15
    option_label_font = ImageFont.truetype(font_path, 30)
    
    # Draw option labels at the start of each option box
    draw.text((opt_a_box[0] + label_margin, opt_a_box[1] + (opt_height - 30) // 2), "A:", font=option_label_font, fill=text_color)
    draw.text((opt_b_box[0] + label_margin, opt_b_box[1] + (opt_height - 30) // 2), "B:", font=option_label_font, fill=text_color)
    draw.text((opt_c_box[0] + label_margin, opt_c_box[1] + (opt_height - 30) // 2), "C:", font=option_label_font, fill=text_color)
    draw.text((opt_d_box[0] + label_margin, opt_d_box[1] + (opt_height - 30) // 2), "D:", font=option_label_font, fill=text_color)
    
    # Adjust option regions to account for the labels
    label_width = option_label_font.getbbox("X:")[2] - option_label_font.getbbox("X:")[0]
    opt_a_text_region = (opt_a_box[0] + label_width + 2 * label_margin, opt_a_box[1], opt_a_box[2] - label_margin, opt_a_box[3])
    opt_b_text_region = (opt_b_box[0] + label_width + 2 * label_margin, opt_b_box[1], opt_b_box[2] - label_margin, opt_b_box[3])
    opt_c_text_region = (opt_c_box[0] + label_width + 2 * label_margin, opt_c_box[1], opt_c_box[2] - label_margin, opt_c_box[3])
    opt_d_text_region = (opt_d_box[0] + label_width + 2 * label_margin, opt_d_box[1], opt_d_box[2] - label_margin, opt_d_box[3])
    
    # Set font sizes - question font is always larger than options
    question_font_size = 45
    option_font_size = 30
    
    # Create fonts - with possibility to adjust question font size if needed
    question_font = adjust_font_size(
        question_text, 
        font_path, 
        question_font_size, 
        q_box_region[2] - q_box_region[0] - 20, 
        q_box_region[3] - q_box_region[1] - 20
    )
    option_font = ImageFont.truetype(font_path, option_font_size)
    
    # Draw text with wrapping
    # For question, provide inner padding
    question_inner_region = (
        q_box_region[0] + 15, 
        q_box_region[1] + 10, 
        q_box_region[2] - 15, 
        q_box_region[3] - 10
    )
    draw_centered_wrapped_text(draw, question_inner_region, question_text, question_font, text_color)
    draw_centered_wrapped_text(draw, opt_a_text_region, opt_a_text[2:] if opt_a_text.startswith("a)") else opt_a_text, option_font, text_color)
    draw_centered_wrapped_text(draw, opt_b_text_region, opt_b_text[2:] if opt_b_text.startswith("b)") else opt_b_text, option_font, text_color)
    draw_centered_wrapped_text(draw, opt_c_text_region, opt_c_text[2:] if opt_c_text.startswith("c)") else opt_c_text, option_font, text_color)
    draw_centered_wrapped_text(draw, opt_d_text_region, opt_d_text[2:] if opt_d_text.startswith("d)") else opt_d_text, option_font, text_color)
    
    # Convert background with text to numpy array and create base clip (13 sec)
    base_img_np = np.array(bg_img)
    base_clip = ImageClip(base_img_np).with_duration(13)
    base_clip = FadeIn(1).apply(base_clip)
    
    # Process timer video clip (actual duration: 11.56 sec)
    def remove_green(frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        lower_green = np.array([40, 40, 40])
        upper_green = np.array([90, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        alpha = np.where(mask == 255, 0, 255).astype(np.uint8)
        frame_rgba = cv2.cvtColor(frame, cv2.COLOR_RGB2RGBA)
        frame_rgba[:, :, 3] = alpha
        return frame_rgba

    original_timer_clip = timer_clip
    def new_frame(t):
        frame = original_timer_clip.get_frame(t)
        return remove_green(frame)
    
    timer_clip = VideoClip(new_frame, duration=original_timer_clip.duration)
    timer_clip = timer_clip.with_audio(original_timer_clip.audio)
    
    # Resize timer clip
    timer_clip = timer_clip.resized((timer_width, timer_height))
    
    # Position timer at top center
    timer_clip = timer_clip.with_position(timer_position)
    
    # Find the correct option box based on the answer
    answer_lower = answer_text.lower().strip()
    answer_box = None
    if "a)" in answer_lower or answer_lower.startswith("a"):
        answer_box = opt_a_box
    elif "b)" in answer_lower or answer_lower.startswith("b"):
        answer_box = opt_b_box
    elif "c)" in answer_lower or answer_lower.startswith("c"):
        answer_box = opt_c_box
    elif "d)" in answer_lower or answer_lower.startswith("d"):
        answer_box = opt_d_box
    
    # Create blinking green answer overlay
    blinking_frames = []
    blink_duration = 3  # 3 seconds of blinking
    fps = 24  # frames per second
    blink_frames = blink_duration * fps
    blink_period = 8  # frames on, frames off
    
    for frame_num in range(blink_frames):
        # Create a transparent overlay
        blink_img = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
        blink_draw = ImageDraw.Draw(blink_img)
        
        # Only draw the green highlight on alternating frames (for blinking effect)
        if answer_box and (frame_num % blink_period < blink_period // 2):
            # Bright green highlight for correct answer
            green_color = (0, 255, 0, 200)  # Bright green with some transparency
            # Fill the answer box with green
            blink_draw.rounded_rectangle(answer_box, radius=box_radius, fill=green_color, outline=green_color, width=3)
            
            # Add the option label back on top
            label_x = answer_box[0] + label_margin
            label_y = answer_box[1] + (opt_height - 30) // 2
            
            # Determine which option label to use
            if answer_box == opt_a_box:
                label_text = "A:"
            elif answer_box == opt_b_box:
                label_text = "B:"
            elif answer_box == opt_c_box:
                label_text = "C:"
            elif answer_box == opt_d_box:
                label_text = "D:"
            else:
                label_text = ""
                
            blink_draw.text((label_x, label_y), label_text, font=option_label_font, fill=text_color)
            
            # Add the option text back on top
            if answer_box == opt_a_box:
                option_text = opt_a_text[2:] if opt_a_text.startswith("a)") else opt_a_text
                text_region = opt_a_text_region
            elif answer_box == opt_b_box:
                option_text = opt_b_text[2:] if opt_b_text.startswith("b)") else opt_b_text
                text_region = opt_b_text_region
            elif answer_box == opt_c_box:
                option_text = opt_c_text[2:] if opt_c_text.startswith("c)") else opt_c_text
                text_region = opt_c_text_region
            elif answer_box == opt_d_box:
                option_text = opt_d_text[2:] if opt_d_text.startswith("d)") else opt_d_text
                text_region = opt_d_text_region
            else:
                option_text = ""
                text_region = (0, 0, 0, 0)
                
            draw_centered_wrapped_text(blink_draw, text_region, option_text, option_font, text_color)
            
        blinking_frames.append(np.array(blink_img))
    
    # Create the blinking effect clip
    def make_blink_frame(t):
        frame_idx = int(t * fps) % len(blinking_frames)
        return blinking_frames[frame_idx]
    
    blink_clip = VideoClip(make_blink_frame, duration=blink_duration).with_start(10)
    
    # Composite all layers: base, timer, and blinking answer overlay
    final_clip = CompositeVideoClip([base_clip, timer_clip, blink_clip]).with_duration(13)
    return final_clip

### Main Block ###
if __name__ == "__main__":
    # Ask user for video ratio selection
    print("Select video ratio:")
    print("Enter 1 for 16:9 (default) or 2 for 9:16 (vertical)")
    ratio_choice = input().strip()
    if ratio_choice == "2":
        vertical_layout = True
        video_width = 720
        video_height = 1280
    else:
        vertical_layout = False
        video_width = 1280
        video_height = 720

    # Get interactive quiz input from user
    print("\nEnter your quiz questions now:")
    quiz_text = get_quiz_input()
    questions = parse_quiz_text(quiz_text)
    if not questions:
        sys.exit("No valid questions were entered.")
    
    clips = []
    for idx, q in enumerate(questions):
        clip = make_quiz_clip(q["question"], q["opt_a"], q["opt_b"], q["opt_c"], q["opt_d"], q["answer"])
        clips.append(clip)
        output_path = f"/storage/emulated/0/OUTPUT/quiz_clip{idx+1}.mp4"
        clip.write_videofile(output_path, fps=24)
        print(f"Clip {idx+1} saved to: {output_path}")
    
    # Concatenate all clips into a final video
    final_clip = concatenate_videoclips(clips)
    final_output_path = "/storage/emulated/0/OUTPUT/final_quiz.mp4"
    final_clip.write_videofile(final_output_path, fps=24)
    print("Final combined video saved to:", final_output_path)
