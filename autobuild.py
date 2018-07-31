#!/usr/bin/env python
# -*- coding:utf-8 -*-

# ./autobuild.py -p youproject.xcodeproj -s schemename
# ./autobuild.py -w youproject.xcworkspace -s schemename

import argparse
import subprocess
import requests
import os
import zipfile, sys, re
import biplist
import shutil
from plistlib import *
import datetime, time

# 支持python2.7

# configuration for iOS build setting
CONFIGURATION = "Release"
EXPORT_OPTIONS_PLIST = "exportOptions.plist"
# 会在桌面创建输出ipa文件的目录
EXPORT_MAIN_DIRECTORY = "~/Desktop/"
# 会在桌面创建输出archive文件的目录
EXPORT_ARCHIVE_DIRECTORY = "~/Library/Developer/Xcode/Archives"
# 自动打包配置文件，要打多少包，打什么包在这里配置
EXPORT_AUTOBUILD_PLIST = "autobuild.plist"
# 项目工程读取工程里面的配置文件
EXPORT_CONFIG_PLIST = "config.plist"
# 签名证书用于重签名
VERIFY_IDENTIFY_FILE = "iPhone Distribution: Guangzhou Honghai Network Technology Development Co.,Ltd"
# 项目名称
PROJECT_NAME = "vwork"

# 蒲公英配置
PGYER_UPLOAD_URL = "https://qiniu-storage.pgyer.com/apiv1/app/upload"
DOWNLOAD_BASE_URL = "https://www.pgyer.com"
USER_KEY = "dc6b80fd61f9f68d4db3bee087e042d2"
API_KEY = "037f4075240d290a6d8d61f6c6a3bc3f"
# 版本更新描述
UPDATE_DESCRIPTION = ""
# 设置从蒲公英下载应用时的密码
PYGER_PASSWORD = ""


def cleanArchiveFile(archiveFile):
    cleanCmd = "rm -r %s" % (archiveFile)
    process = subprocess.Popen(cleanCmd, shell=True)
    process.wait()
    print "cleaned archiveFile: %s" % (archiveFile)


def parserUploadResult(jsonResult):
    resultCode = jsonResult['code']
    if resultCode == 0:
        downUrl = DOWNLOAD_BASE_URL + "/" + jsonResult['data']['appShortcutUrl']
        print "Upload Success"
        print "DownUrl is:" + downUrl
    else:
        print "Upload Fail!"
        print "Reason:" + jsonResult['message']


# 上传到蒲公英
def uploadIpaToPgyer(ipaPath):
    print "ipaPath:" + ipaPath


#    ipaPath = os.path.expanduser(ipaPath)
#    ipaPath = unicode(ipaPath, "utf-8")
#    files = {'file': open(ipaPath, 'rb')}
#    headers = {'enctype':'multipart/form-data'}
#    payload = {'uKey':USER_KEY,'_api_key':API_KEY,'installType':'1','updateDescription':UPDATE_DESCRIPTION, 'password':PYGER_PASSWORD}
#    print "uploading...."
#    r = requests.post(PGYER_UPLOAD_URL, data = payload ,files=files,headers=headers)
#    if r.status_code == requests.codes.ok:
#         result = r.json()
#         parserUploadResult(result)
#    else:
#        print 'HTTPError,Code:'+r.status_code
# 获取配置文件
def find_config_path(zip_file):
    name_list = zip_file.namelist()
    pattern = re.compile(r'Payload/[^/]*.app/' + EXPORT_CONFIG_PLIST)
    for path in name_list:
        m = pattern.match(path)
        if m is not None:
            return m.group()


# 打包完成之后获取自动打包配置
def find_autobuild_path(zip_file):
    name_list = zip_file.namelist()
    pattern = re.compile(r'Payload/[^/]*.app/' + EXPORT_AUTOBUILD_PLIST)
    for path in name_list:
        m = pattern.match(path)
        if m is not None:
            return m.group()


# 更换app的图标和启动页
def copyNewIcon(fromPath, toPath):
    if os.path.exists(fromPath) == False:
        print('不存在这个文件夹,无需替换图标！')
    else:
        for root, dirs, files in os.walk(fromPath):
            for i in range(len(files)):
                print(files[i])
                if (files[i][-3:] == 'jpg') or (files[i][-3:] == 'png') or (files[i][-3:] == 'JPG'):
                    file_path = root + '/' + files[i]
                    new_file_path = toPath + '/' + files[i]
                    shutil.copy(file_path, new_file_path)


def exportOtherIpa(ipa_path):
    # 解压缩打出的包读取配置文件，根据自动打包配置文件去复制修改最终要打的包
    ipa_path = os.path.expanduser(ipa_path)
    print ipa_path
    ipa_file = zipfile.ZipFile(ipa_path)
    plist_path = find_autobuild_path(ipa_file)

    current_path = os.path.split(ipa_path)[0]
    # 1.解压母包
    unzipCmd = 'cd %s;unzip %s' % (current_path, PROJECT_NAME + '.ipa')
    process = subprocess.Popen(unzipCmd, shell=True)
    process.wait()
    appFile = PROJECT_NAME + '.app'
    # 2.根据母包里面mobileprovision生成entitlements.plist
    entitlementsCmd = 'security cms -D -i %s > %s;/usr/libexec/PlistBuddy -x -c \'Print:Entitlements\' %s > %s' % (
    os.path.join(current_path, 'Payload/' + appFile + '/embedded.mobileprovision'),
    os.path.join(current_path, 'entitlements_full.plist'), os.path.join(current_path, 'entitlements_full.plist'),
    os.path.join(current_path, 'entitlements.plist'))
    process1 = subprocess.Popen(entitlementsCmd, shell=True)
    process1.wait()
    # 读取母包里面配置文件
    plist_data = ipa_file.read(plist_path)
    plist_root = biplist.readPlistFromString(plist_data)
    ipa_file.close()
    pwd = os.getcwd()
    for item in plist_root['items']:
        # 要打的包
        if item['build'] == True:
            # 3.复制母包
            shutil.copytree(os.path.join(current_path, 'Payload'), os.path.join(current_path, 'childIpa/Payload'))
            # 4.修改子包配置文件
            writePlist(item, os.path.join(current_path, 'childIpa/Payload/' + appFile + '/' + EXPORT_CONFIG_PLIST))
            # 5.替换app包的icon和启动页,本地以APPID为文件名存放自定义图标
            iconFromPath = os.path.join(os.path.abspath(os.path.dirname(
                pwd) + os.path.sep + ".." + os.path.sep + ".." + os.path.sep + ".." + os.path.sep + ".."),
                                        item['AppId'])
            copyNewIcon(iconFromPath, os.path.join(current_path, 'childIpa/Payload/' + appFile))
            # 6.修改APP名称
            if item['AppName'] is not None:
                # os.system('/usr/libexec/PlistBuddy -c "Set:CFBundleVersion %s" %s' % (
                #     item['AppName'], os.path.join(current_path, 'childIpa/Payload/' + appFile + '/Info.plist')))
                os.system('/usr/libexec/PlistBuddy -c "Set:CFBundleDisplayName %s" %s' % (
                    item['AppName'], os.path.join(current_path, 'childIpa/Payload/' + appFile + '/Info.plist')))
            # 7.根据entitlements.plist重新签名
            codesignCmd = '/usr/bin/codesign --continue -f -s \"%s\" --entitlements \"%s\" %s' % (
            VERIFY_IDENTIFY_FILE, os.path.join(current_path, 'entitlements.plist'),
            os.path.join(current_path, 'childIpa/Payload/' + appFile))
            print codesignCmd
            process2 = subprocess.Popen(codesignCmd, shell=True)
            process2.wait()
            # 多线程签名，要等线程运行完之后再打包，否则打出的包会安装失败
            (stdoutdata, stderrdata) = process2.communicate()
            signReturnCode = process2.returncode
            if signReturnCode != 0:
                print 'resign failed!'
            else:
                # 8.压缩导出ipa包
                zipCmd = 'cd %s;zip -r %s Payload' % (
                os.path.join(current_path, 'childIpa'), item['ProjectName'] + '.ipa')
                process3 = subprocess.Popen(zipCmd, shell=True)
                process3.wait()
                # 8.生成子包后删除压缩文件
                shutil.rmtree(os.path.join(current_path, 'childIpa/Payload'))


# 创建输出ipa文件路径: ~/Desktop/{scheme}{2016-12-28_08-08-10}
def buildExportDirectory(scheme):
    dateCmd = 'date "+%Y-%m-%d_%H-%M-%S"'
    process = subprocess.Popen(dateCmd, stdout=subprocess.PIPE, shell=True)
    (stdoutdata, stderrdata) = process.communicate()
    exportDirectory = "%s%s%s" % (EXPORT_MAIN_DIRECTORY, scheme, stdoutdata.strip())
    return exportDirectory


def buildArchivePath(tempName):
    dateCmd = 'date "+%Y%m%d%H%M"'
    process = subprocess.Popen(dateCmd, stdout=subprocess.PIPE, shell=True)
    (stdoutdata, stderrdata) = process.communicate()
    archiveName = "%s.xcarchive" % (tempName + stdoutdata.strip())
    archivePath = EXPORT_ARCHIVE_DIRECTORY + '/' + archiveName
    return archivePath


def getIpaPath(exportPath):
    cmd = "ls %s" % (exportPath)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    (stdoutdata, stderrdata) = process.communicate()
    ipaName = stdoutdata.strip()
    # xcode 9 之后这个ipaName有变化
    ipaPath = exportPath + "/" + PROJECT_NAME + '.ipa'
    return ipaPath


def exportArchive(scheme, archivePath):
    exportDirectory = buildExportDirectory(scheme)
    exportCmd = "xcodebuild -exportArchive -archivePath %s -exportPath %s -exportOptionsPlist %s" % (
    archivePath, exportDirectory, EXPORT_OPTIONS_PLIST)
    process = subprocess.Popen(exportCmd, shell=True)
    (stdoutdata, stderrdata) = process.communicate()

    signReturnCode = process.returncode
    if signReturnCode != 0:
        print "export %s failed" % (scheme)
        return ""
    else:
        return exportDirectory


# 不使用cocoapods
def buildProject(project, scheme):
    archivePath = buildArchivePath(scheme)
    print "archivePath: " + archivePath
    archiveCmd = 'xcodebuild -project %s -scheme %s -configuration %s archive -archivePath %s -destination generic/platform=iOS' % (
    project, scheme, CONFIGURATION, archivePath)
    process = subprocess.Popen(archiveCmd, shell=True)
    process.wait()

    archiveReturnCode = process.returncode
    if archiveReturnCode != 0:
        print "archive workspace %s failed" % (workspace)
        cleanArchiveFile(archivePath)
    else:
        exportDirectory = exportArchive(scheme, archivePath)
        cleanArchiveFile(archivePath)
        if exportDirectory != "":
            ipaPath = getIpaPath(exportDirectory)
            uploadIpaToPgyer(ipaPath)


# 使用cocoapods
def buildWorkspace(workspace, scheme):
    archivePath = buildArchivePath(scheme)
    print "archivePath: " + archivePath
    archiveCmd = 'xcodebuild -workspace %s -scheme %s -configuration %s archive -archivePath %s -destination generic/platform=iOS' % (
    workspace, scheme, CONFIGURATION, archivePath)
    process = subprocess.Popen(archiveCmd, shell=True)
    process.wait()

    archiveReturnCode = process.returncode
    if archiveReturnCode != 0:
        print "archive workspace %s failed" % (workspace)
        cleanArchiveFile(archivePath)
    else:
        exportDirectory = exportArchive(scheme, archivePath)
        # cleanArchiveFile(archivePath)
        if exportDirectory != "":
            ipaPath = getIpaPath(exportDirectory)
            # 打完一个包之后，解压，然后复制n个包，分别修改包里面的配置文件，然后再重新签名压缩打包，以达到快速批量打包的目的
            exportOtherIpa(ipaPath)


def xcbuild():
    pwd = os.getcwd()
    workspace = os.path.join(os.path.abspath(os.path.dirname(pwd) + os.path.sep + ".." + os.path.sep + ".."),
                             PROJECT_NAME + ".xcworkspace")
    project = None
    scheme = PROJECT_NAME

    if project is None and workspace is None:
        pass
    elif project is not None:
        buildProject(project, scheme)
    elif workspace is not None:
        buildWorkspace(workspace, scheme)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--workspace", help="Build the workspace name.xcworkspace.", metavar="name.xcworkspace")
    parser.add_argument("-p", "--project", help="Build the project name.xcodeproj.", metavar="name.xcodeproj")
    parser.add_argument("-s", "--scheme",
                        help="Build the scheme specified by schemename. Required if building a workspace.",
                        metavar="schemename")

    options = parser.parse_args()

    xcbuild()


if __name__ == '__main__':
    main()
