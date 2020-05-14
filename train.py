import torchvision.transforms as transforms
from torch.utils.data import DataLoader
from torch.autograd import Variable
from torchvision.utils import save_image

import torch
import torch.nn as nn 
import torch.nn.functional as F

from PIL import Image
import numpy as np

from model import Net1
from model import Network
from model import Net2


from datasets import ImageDataSet

import time
from options import opt

import pytorch_ssim
import itertools

import matplotlib.pyplot as plt

import cv2




def save_images(batches_done, dataloader, net):
    Tensor = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor    

    """Saves a generated sample from the validation set"""
    imgs = next(iter(dataloader))
    hz = Variable(imgs["hz"].type(Tensor))
    gt = Variable(imgs["gt"].type(Tensor))
    dehaze = net(hz)
    img_sample = torch.cat((hz.data, gt.data, dehaze.data), -2)
    save_image(img_sample, "images/%s_{}.png".format(imgs["index"]) % (batches_done), nrow=5, normalize=True)


def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        torch.nn.init.normal(m.weight.data, 0.0, 0.02)
    elif classname.find('InstanceNorm2d') != -1:
        torch.nn.init.normal(m.weight.data, 1.0, 0.02)
        torch.nn.init.constant(m.bias.data, 0.0)

def train():

    print(opt)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # net = Net2(opt.input_nc, opt.output_nc)
    # net = Network(opt.input_nc, opt.output_nc)
    net = Net1(opt.input_nc, opt.output_nc)
    # UNet = UNet(opt.input_nc, opt.output_nc)

    if opt.epoch != 0:
        net.load_state_dict(torch.load('./checkpoints/generator_{}.pth'.format(opt.epoch)))
        print("Load Model Epoch : {}".format(opt.epoch))
        net.to(device)

    if torch.cuda.is_available():
        print("Use GPU")
        net = net.cuda()
    # net.apply(weights_init)
    # Loss
    criterion_edge = torch.nn.L1Loss().to(device)
    criterion_pixel = torch.nn.L1Loss().to(device)
    
    # Optimizer
    optimizer = torch.optim.Adam(net.parameters(), lr=opt.lr, betas=(0.5, 0.999))

    # Input
    Tensor = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor    
    input_hz = Tensor(opt.batch_size, opt.input_nc)

    # Dataset Loader
    transforms_ = [
        transforms.Resize((opt.img_height, opt.img_width), Image.BICUBIC),
        transforms.ToTensor(),
        transforms.Normalize((0.5,0.5,0.5),(0.5,0.5,0.5))
    ]
    dataloader = DataLoader(
        ImageDataSet(opt.dataroot, transforms_=transforms_),
        batch_size=opt.batch_size, 
        shuffle=True,
        num_workers=opt.num_workers
    )
    print("Number of training images: {}".format(len(dataloader)))

    start_time = time.time() 
    prev_time = start_time

    loss_list = []

    for epoch in range(opt.epoch, opt.epoch + opt.n_epochs):
        temp_loss_list = []        
        print('Epoch {}/{}'.format(epoch + 1, opt.n_epochs))
        print('-' * 70)
        for i, batch in enumerate(dataloader):
            
            # input
            gt = Variable(batch['gt'].type(Tensor))
            hz = Variable(batch['hz'].type(Tensor))
            
            #############################
            #         NetWork         #
            #############################
            optimizer.zero_grad()
            dehaze = net(hz)

            # Compute Edge Loss
            sobel = torch.Tensor(np.array([[
                [
                [-1,0,1],
                [-2,0,2],                
                [-1,0,1]
                ],
                [
                [-1,0,1],
                [-2,0,2],                
                [-1,0,1]
                ],
                [
                [-1,0,1],
                [-2,0,2],                
                [-1,0,1]
                ],
            ]], dtype=np.float64)).cuda()

            # edge_hz = F.conv2d(hz, sobel, padding=1)
            edge_dhz = F.conv2d(dehaze, sobel, padding=1)
            edge_gt = F.conv2d(gt, sobel, padding=1)
            
            # edge_loss = criterion_edge(edge_dhz, edge_gt)

            loss_l1 = criterion_pixel(dehaze, gt)
            # loss_mse = criterion_content(dehaze, gt)
            loss_ssim = 1 - pytorch_ssim.ssim(dehaze, gt)
            loss_edge = criterion_edge(edge_dhz, edge_gt)
            
            # loss_l1 = loss_l1                   # L1 Loss: [0, 1]   
            # loss_ssim = loss_ssim               # SSIM Loss: [0, 1]
                                                  # 0 : 1 : 1
            loss = 0 * loss_ssim + 1 * loss_l1 + loss_edge    # Nomalize [0, 1] 
            loss.backward()
            optimizer.step()

            #######################################################################
            ############################### To Test ############################### 
            ############################## Show Edge ############################## 
            #######################################################################

            # test_hz = edge_hz.cpu().detach().numpy()
            # test_hz = np.array([test_hz[0][0], test_hz[0][0], test_hz[0][0]])
            # test_dhz = edge_dhz.cpu().detach().numpy()
            # test_dhz = np.array([test_dhz[0][0], test_dhz[0][0], test_dhz[0][0]])
            # test_gt = edge_gt.cpu().detach().numpy()
            # test_gt = np.array([test_gt[0][0], test_gt[0][0], test_gt[0][0]])

            # print(edge_loss.data)
            # print(pixel_loss.data)

            # plt.subplot(2,3,1)
            # plt.imshow(np.transpose(test_hz, (1,2,0)), interpolation="bicubic")
            # plt.subplot(2,3,2)
            # plt.imshow(np.transpose(test_dhz, (1,2,0)), interpolation="bicubic")
            # plt.subplot(2,3,3)
            # plt.imshow(np.transpose(test_gt, (1,2,0)), interpolation="bicubic")
            # plt.subplot(2,3,4)
            # plt.imshow(np.transpose(hz.cpu().detach().numpy()[0], (1,2,0)), interpolation="bicubic")
            # plt.subplot(2,3,5)
            # plt.imshow(np.transpose(dehaze.cpu().detach().numpy()[0], (1,2,0)), interpolation="bicubic")
            # plt.subplot(2,3,6)
            # plt.imshow(np.transpose(gt.cpu().detach().numpy()[0], (1,2,0)), interpolation="bicubic")
            # plt.show()
            # break
            #######################################################################

            #############################
            #            Log            #
            #############################
            batches_done = epoch * len(dataloader) + i
            time_left = time.time() - prev_time

            print( "[Epoch %d/%d] [Data %d/%d] [SSIM Loss: %f L1 Loss: %f Edge Loss: %f TOTAL Loss: %f] [TIME: %.4s]"
            % (
                (1 + epoch),
                opt.n_epochs,
                i,
                len(dataloader),
                loss_ssim.item(),
                loss_l1.item(),
                loss_edge.item(),
                loss,
                time_left
            ))
            prev_time = time.time()
            if batches_done % 100 == 0:
                save_images(batches_done, dataloader, net)

            temp_loss_list.append(loss.item())
            # if batches_done % 10 == 0:
            #     print(temp_loss_list)
            #     plt.plot(temp_loss_list)
            #     plt.show()
                
        # Save model checkpoints
        torch.save(net.state_dict(), "./checkpoints/checkpoint_%d.pth" % (epoch + 1))
        print("Save model Epoch{}".format(epoch + 1))

        loss_list.append(np.mean(temp_loss_list))


    end_time = time.time() - start_time
    print('Training complete in {:.0f}m {:.0f}s'.format(end_time // 60, end_time % 60))

    # Validate


    # Loss Graph
    plt.plot(loss_list)
    plt.show()


if __name__ == '__main__':
    train()