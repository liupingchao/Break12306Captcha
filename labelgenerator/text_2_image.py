# encoding: UTF-8
from __future__ import unicode_literals
import random
import string
import numpy as np
from PIL import Image
import argparse

PIXEL_DEPTH = 255


def trim_label(img, size=227):
    width, height = img.size
    new_height = size / max(width, height) * height
    img = img.resize((size, new_height))
    result = Image.new('L', (size, size), 255)
    result.paste(img, (0, (size - new_height) // 2))
    return result


def shrink_space(img):
    # crop with min_box
    matrix = np.array(img.convert("L"))
    matrix = np.where(matrix > 200, 0, 1)
    col_hist = np.sum(matrix, 0)
    row_hist = np.sum(matrix, 1)
    left, right, top, bot = 0, len(col_hist) - 1, 0, len(row_hist) - 1
    while col_hist[left] == 0 and left < right: left += 1
    while col_hist[right] == 0 and left < right: right -= 1
    while row_hist[top] == 0 and top < bot: top += 1
    while row_hist[bot] == 0 and top < bot: bot -= 1
    img = img.crop((left, top, right, bot))

    _, height = img.size

    matrix = np.array(img.convert("L"))
    matrix = np.where(matrix > 200, 0, 1)
    col_hist = np.sum(matrix, 0)

    intervals = list()
    l, r = 0, 0
    final_width = 0
    while l < len(col_hist):
        while r < len(col_hist) and col_hist[r]:
            r += 1
        intervals.append((l, r,))
        final_width += r - l + 1
        l = r + 1
        while l < len(col_hist) and not col_hist[l]:
            l += 1
        r = l

    result = Image.new('L', (final_width, height), 255)
    cur_col = 0
    for l, r in intervals:
        result.paste(img.crop((l, 0, r, height - 1)), (cur_col, 0))
        cur_col += r - l + 1
    return result


def get_random_string(length=5):
    return unicode("".join([random.choice(string.uppercase \
                                          + string.lowercase \
                                          + string.digits)
                            for i in range(length)]))


def add_noise_to_phrase(phrase):
    """
    Args
        phrase: Chinese phrase encoded in UTF8
    Return
        A Chinese phrase added with noise
    """
    prob_noise = 0.2
    if random.random() > prob_noise:
        return phrase
    noise_char = list(u'''~·^*-_"`',."''')
    phrase = list(phrase)
    length = len(phrase)
    pos = random.randint(0, length)  # [0, length] inclusive
    # print "before", phrase
    phrase.insert(pos, random.sample(noise_char, 1)[0])
    # print "after", phrase
    return unicode(u"".join(phrase))


def load_chinese_phrases(path="./labels.txt"):
    chinese_phrases = []
    with open(path) as reader:
        for line in reader:
            # please decode with `utf8`
            chinese_phrases.append(line.strip().split()[0].decode("utf8"))
    print "%d Chinese phrases are loaded" % len(chinese_phrases)
    return chinese_phrases


def text_2_distorted_image(text,
                           image_dir_path="./images",
                           font_size=20,
                           left_right_padding=10,
                           up_down_padding=5,
                           noise_char=True,
                           show=False,
                           save=False):
    """ Units are all pixels"""
    import os
    import StringIO
    from PIL import Image  # pip install pillow
    import pygame
    import numpy as np
    pygame.init()

    if isinstance(text, str):
        text = text.decode("utf8")

    original_text = text
    text = add_noise_to_phrase(text)
    num_characters = len(text)

    width = left_right_padding * 2 + num_characters * font_size
    height = up_down_padding * 2 + font_size  # just one line

    image = Image.new(mode="RGB", size=(width, height), color=(255, 255, 255))

    def letter_2_string_io(letter):
        font_list = ["simsun.ttc", "black.ttf", "youyuan.ttf", "kai.ttf"]
        selected_font = font_list[random.randint(0, len(font_list) - 1)]

        font = pygame.font.Font(os.path.join("fonts", selected_font), font_size)
        rendered_letter = font.render(letter, True, (0, 0, 0), (255, 255, 255))

        letter_string_io = StringIO.StringIO()
        pygame.image.save(rendered_letter, letter_string_io)
        return letter_string_io

    for i in xrange(len(text)):
        letter_io = letter_2_string_io(text[i])
        letter_io.seek(0)
        line = Image.open(letter_io)
        image.paste(line, (left_right_padding + i * font_size, up_down_padding))

    image_arr = np.array(image)

    height, width, _ = image_arr.shape

    # this is a decorator
    def get_sin_shift(amplitude, frequency, phase=None):
        if phase is None:
            phase = random.random() * np.pi

        def sin_shift(x):
            return amplitude * np.sin(2.0 * np.pi * x * frequency + phase)

        return sin_shift

    # TODO: 字体大小随机
    # - Vertical shift

    sin_amplitude = height / 3.5
    sin_frequency = float(len(text)) / width

    vertical_shift = get_sin_shift(sin_amplitude, sin_frequency)

    for i in xrange(width):
        image_arr[:, i] = np.roll(image_arr[:, i], int(vertical_shift(i)))

    # - Horizontal shift

    sin_amplitude = width / 20.0
    sin_frequency = 1.0 / height

    horizontal_shift = get_sin_shift(sin_amplitude, sin_frequency)
    for j in xrange(height):
        image_arr[j, :] = np.roll(image_arr[j, :], int(horizontal_shift(j)))

    image = shrink_space(Image.fromarray(image_arr).convert("L"))

    filename = u"%s_%s.png" % (original_text, get_random_string())

    image = trim_label(image)

    if show:
        image.show()

    if save:
        path = os.path.join(image_dir_path, filename)
        # print "Saving file to " + path
        image.save(path)

    return image


def generate_bin_datafile(phrases,
                          data_path,
                          label_path,
                          num_per_phrase=10,
                          img_size=60):
    # phrases = load_chinese_phrases()
    x = np.zeros((num_per_phrase * len(phrases), img_size ** 2))
    y = np.zeros(num_per_phrase * len(phrases))
    sample_order = list()
    for i in range(len(phrases)):
        sample_order.extend([i] * num_per_phrase)
    random.shuffle(sample_order)
    print ("Start Generating....")
    f_data = open(data_path, "w")
    f_label = open(label_path, "w")
    for i, label_index in enumerate(sample_order):
        phrase = phrases[sample_order[i]]
        # print (u"Label %d: %s" % (i, phrase))
        if (i + 1) % 1000 == 0:
            print ("%d / %d: %.2f%% generated" % (i + 1,
                                                  len(sample_order),
                                                  100. * i / len(sample_order)))
        y[i] = label_index
        img = trim_label(text_2_distorted_image(phrase))
        vec = np.array(img \
                       .resize((img_size, img_size))) \
            .reshape(img_size ** 2)
        vec = (vec - PIXEL_DEPTH / 2.0) / PIXEL_DEPTH
        x[i, :] = vec
    # x = x.reshape((num_per_phrase * len(phrases), img_size, img_size))
    np.save(data_path, x)
    np.save(label_path, y)
    print ("Done.")


if __name__ == '__main__':
    l = ['胶卷', '订书机', '安全帽', '毛线', '煤油灯', '灯笼', '沙漠', '矿泉水', '烤鸭', '烤鸭', '气球', '红酒', '芒果', '紫砂壶', '花生', '衣架']
    l = ['烤鸭'] * 5
    for p in l:
        text_2_distorted_image(p, save=True)

    import sys

    sys.exit(0)

    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()

    mode.add_argument("-d", "--demo", action="store_true",
                      help="generate n sample CAPTCHAs and show")
    mode.add_argument("-b", "--binary", action="store_true",
                      help="generate binary numpy array data files. \
                        -d, -l must be specified")
    parser.add_argument("-D", "--data", action="store",
                        help="specify the output file for image matrix,\
                        each row is an reshaped image")
    parser.add_argument("-L", "--label", action="store",
                        help="specify the output file for label vector")
    mode.add_argument("-i", "--image", action="store",
                      help="generate label images in specified path")
    parser.add_argument("n", type=int,
                        help="specify the number of CAPTCHA to generate, \
                        default 1. For -b, n is the number for each category.")

    args = parser.parse_args()
    # print args
    if args.demo or args.image:
        phrases = load_chinese_phrases()
        generate_number = args.n
        for cur_phrase in phrases:
            print cur_phrase
            for i in range(generate_number):
                display_phrase = add_noise_to_phrase(cur_phrase)
                text_2_distorted_image(text=cur_phrase, show=args.demo,
                                       save=bool(args.image),
                                       image_dir_path=args.image)
    elif args.binary:
        if not args.data or not args.label:
            print ("-D, -L must be specified")
            quit()
        phrases = load_chinese_phrases()
        generate_number = args.n
        generate_bin_datafile(phrases,
                              args.data,
                              args.label,
                              num_per_phrase=generate_number)
