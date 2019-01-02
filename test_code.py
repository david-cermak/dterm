import sys

if len(sys.argv)==2:
    text_file = open("log.txt", "a")
    text_file.write("Received: {}\n".format(sys.argv[1]))
    text_file.close()
