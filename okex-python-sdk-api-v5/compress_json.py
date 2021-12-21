'''
	用于将database里的行情数据进行压缩
	1.隔一段时间遍历一遍文件夹
	2.根据遍历出来的文件夹创建对应的文件夹
	2.将文件夹中超过nMB的文件，并且不是只有该文件时，进行压缩，并且mv到储备文件夹中
'''

# 该文件的作用是删除手机数据中的多余的.json文件
# 效果如下所示
# ├── SHIB-USDT-SWAP
# │   ├── SHIB-USDT-SWAP-11.json
# │   ├── SHIB-USDT-SWAP-12.json
# │   ├── SHIB-USDT-SWAP-13.json
# │   ├── SHIB-USDT-SWAP-14.json
# │   ├── SHIB-USDT-SWAP-15.json
# │   └── SHIB-USDT-SWAP-16.json

# 剩下一个最大号码的文件
#
# ├── SHIB-USDT-SWAP
# │   └── SHIB-USDT-SWAP-16.json

import os,time

market_crawlingPath = os.path.join('..','..','database','market_crawling')
compressFilePath = os.path.join('..','..','database','compressFiles')

while True:
	for root, dirs, files in os.walk(market_crawlingPath):
		# 批量创建各币种文件夹
		if root.endswith('market_crawling'):
			for d in dirs:
				if os.path.isdir(os.path.join(compressFilePath, d)):
					continue
				os.makedirs(os.path.join(compressFilePath, d))
			continue
		
		# 递归遍历各币种文件夹里的文件
		files = sorted(files, key=lambda s: int(s.split('-')[-1].split('.')[0])) #利用数字进行比较 SHIB-USDT-SWAP-19.json
		print(files)

		if len(files)>1:
			dirname = root.split('/')[-1]
			for f in files[:-1]:
				crawFilePath = os.path.join(root, f)
				print(crawFilePath)
				compressDir = os.path.join(compressFilePath, dirname)
				compressFile = os.path.join(compressFilePath, dirname, f)
				os.system(f'mv {crawFilePath} {compressDir}')
				os.system(f'gzip -9 -c {compressFile} > {compressFile}.gz')
				os.system(f'rm {compressFile}')
	time.sleep(1)
