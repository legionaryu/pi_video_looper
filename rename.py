import shutil

targetNames = ["std_1to2.h264", "std_1to3.h264", "std_1to4.h264",
               "std_2to1.h264", "std_2to3.h264", "std_2to4.h264",
               "std_3to1.h264", "std_3to2.h264", "std_3to4.h264",
               "std_4to1.h264", "std_4to2.h264", "std_4to3.h264",
               "alt_1to2.h264", "alt_1to3.h264", "alt_1to4.h264",
               "alt_2to1.h264", "alt_2to3.h264", "alt_2to4.h264",
               "alt_3to1.h264", "alt_3to2.h264", "alt_3to4.h264",
               "alt_4to1.h264", "alt_4to2.h264", "alt_4to3.h264",
               "alt_to_std1.h264",
               "alt_to_std2.h264",
               "alt_to_std3.h264",
               "alt_to_std4.h264",
               "std_to_alt1.h264",
               "std_to_alt2.h264",
               "std_to_alt3.h264",
               "std_to_alt4.h264"]

for name in targetNames:
    print("Copy " + name)
    shutil.copy2("Coffee-53s-slomo.h264", "videos\\" + name)
