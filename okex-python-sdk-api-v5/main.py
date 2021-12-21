import multiprocessing
import os

def process1():
	os.system('python3 websocket_example.py')

def process2():
	os.system('python3 compress_json.py')

if __name__ == '__main__':
	pool = multiprocessing.Pool(processes=2)
	result = []
	result.append(pool.apply_async(process1))
	result.append(pool.apply_async(process2))

	pool.close()
	pool.join()

	for res in result:
		print(f'res.get():{res.get()}')
