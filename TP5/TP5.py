import numpy as np
import scipy.ndimage
import imageio
import matplotlib.pyplot as plt


def compute_data_cost(I1, I2, num_disp_values, Tau):
    """data_cost: a 3D array of sixe height x width x num_disp_value;
    data_cost(y,x,l) is the cost of assigning the label l to pixel (y,x).
    The cost is min(1/3 ||I1[y,x]-I2[y,x-l]||_1, Tau)."""
    h, w, _ = I1.shape
    dataCost = np.zeros((h, w, num_disp_values))
    for y in range(h):
        for x in range(w):
            for l in range(num_disp_values):
               dataCost[y, x, l] = min(
                    (1/3) * np.linalg.norm(I1[y, x] - I2[y, x-l], 1), Tau)
    return dataCost

def compute_energy(dataCost, disparity, Lambda):
    """dataCost: a 3D array of sixe height x width x num_disp_values;
    dataCost(y,x,l) is the cost of assigning the label l to pixel (y,x).
    disparity: array of size height x width containing disparity of each pixel.
    (an integer between 0 and num_disp_values-1)
    Lambda: a scalar value.
    Return total energy, a scalar value"""

    # Data cost
    h, w, _ = dataCost.shape
    y_values, x_values = np.meshgrid(range(h), range(w), indexing='ij')
    costs = dataCost[y_values, x_values, disparity]
    energy = np.sum(costs)

    # Potts Energy
    pottsU = (disparity-np.roll(disparity, -1, axis=0)
              ) != 0  # with the pixel above
    pottsD = (disparity-np.roll(disparity, 1, axis=0)
              ) != 0  # with the pixel below
    pottsL = (disparity-np.roll(disparity, -1, axis=1)
              ) != 0  # with the pixel on the left
    pottsR = (disparity-np.roll(disparity, 1, axis=1)
              ) != 0  # with the pixel on the right

    pottsU[0, :] = 0
    pottsD[h-1, :] = 0
    pottsL[:, 0] = 0
    pottsR[:, w-1] = 0

    potts = pottsU + pottsD + pottsL + pottsR

    energy += Lambda * np.sum(potts)
    return energy


def update_msg(msgUPrev, msgDPrev, msgLPrev, msgRPrev, dataCost, Lambda):
    """Update message maps.
    dataCost: 3D array, depth=label number.
    msgUPrev,msgDPrev,msgLPrev,msgRPrev: 3D arrays (same dims) of old messages.
    Lambda: scalar value
    Return msgU,msgD,msgL,msgR: updated messages"""
    msgU = np.zeros(dataCost.shape)
    msgD = np.zeros(dataCost.shape)
    msgL = np.zeros(dataCost.shape)
    msgR = np.zeros(dataCost.shape)

    h, w, _ = dataCost.shape

    # Incoming messages
    incMsgU = np.roll(msgDPrev, -1, axis=0)
    incMsgD = np.roll(msgUPrev, 1, axis=0)
    incMsgL = np.roll(msgRPrev, -1, axis=1)
    incMsgR = np.roll(msgLPrev, 1, axis=1)

    # Pixels on boundaries of the image
    incMsgU[h-1, :, :] = 0
    incMsgD[0, :, :] = 0
    incMsgL[:, w-1, :] = 0
    incMsgR[:, 0, :] = 0

    # Using question 2

    # First term in the minimum

    AU = dataCost + incMsgD + incMsgL + incMsgR
    AD = dataCost + incMsgU + incMsgL + incMsgR
    AL = dataCost + incMsgU + incMsgD + incMsgR
    AR = dataCost + incMsgU + incMsgD + incMsgL

    # Second term in the minimum
    BU = np.amin(AU, axis=2)
    BD = np.amin(AD, axis=2)
    BL = np.amin(AL, axis=2)
    BR = np.amin(AR, axis=2)

    for l in range(num_disp_values):
        msgU[:, :, l] = np.minimum(AU[:, :, l], Lambda+BU)
        msgD[:, :, l] = np.minimum(AD[:, :, l], Lambda+BD)
        msgL[:, :, l] = np.minimum(AL[:, :, l], Lambda+BL)
        msgR[:, :, l] = np.minimum(AR[:, :, l], Lambda+BR)

    return msgU, msgD, msgL, msgR


def normalize_msg(msgU, msgD, msgL, msgR):
    """Subtract mean along depth dimension from each message"""
    avg = np.mean(msgU, axis=2)
    msgU -= avg[:, :, np.newaxis]
    avg = np.mean(msgD, axis=2)
    msgD -= avg[:, :, np.newaxis]
    avg = np.mean(msgL, axis=2)
    msgL -= avg[:, :, np.newaxis]
    avg = np.mean(msgR, axis=2)
    msgR -= avg[:, :, np.newaxis]
    return msgU, msgD, msgL, msgR


def compute_belief(dataCost, msgU, msgD, msgL, msgR):
    """Compute beliefs, sum of data cost and messages from all neighbors"""
    beliefs = dataCost.copy() + msgU + msgD + msgL + msgR
    return beliefs


def MAP_labeling(beliefs):
    """Return a 2D array assigning to each pixel its best label from beliefs
    computed so far"""
    return np.argmin(beliefs, axis=2)


def stereo_bp(I1, I2, num_disp_values, Lambda, Tau=15, num_iterations=60):
    """The main function"""
    dataCost = compute_data_cost(I1, I2, num_disp_values, Tau)
    energy = np.zeros((num_iterations))  # storing energy at each iteration
    # The messages sent to neighbors in each direction (up,down,left,right)
    h, w, _ = I1.shape
    msgU = np.zeros((h, w, num_disp_values))
    msgD = np.zeros((h, w, num_disp_values))
    msgL = np.zeros((h, w, num_disp_values))
    msgR = np.zeros((h, w, num_disp_values))

    for iter in range(num_iterations):
        msgU, msgD, msgL, msgR = update_msg(
            msgU, msgD, msgL, msgR, dataCost, Lambda)
        msgU, msgD, msgL, msgR = normalize_msg(msgU, msgD, msgL, msgR)
        # Next lines unused for next iteration, could be done only at the end
        beliefs = compute_belief(dataCost, msgU, msgD, msgL, msgR)
        disparity = MAP_labeling(beliefs)
        energy[iter] = compute_energy(dataCost, disparity, Lambda)
    return disparity, energy


# Input
img_left = imageio.imread('tsukuba/imL.png')
img_right = imageio.imread('tsukuba/imR.png')
plt.subplot(121)
plt.imshow(img_left)
plt.subplot(122)
plt.imshow(img_right)
plt.show()

# Convert as float gray images
img_left = img_left.astype(float)
img_right = img_right.astype(float)

# Parameters
num_disp_values = 16  # these images have disparity between 0 and 15.
Lambda = 10.0

# Gaussian filtering
I1 = scipy.ndimage.filters.gaussian_filter(img_left, 0.6)
I2 = scipy.ndimage.filters.gaussian_filter(img_right, 0.6)

disparity, energy = stereo_bp(I1, I2, num_disp_values, Lambda)
imageio.imwrite('disparity_{:g}.png'.format(Lambda), disparity)

# Plot results
plt.subplot(121)
plt.plot(energy)
plt.subplot(122)
plt.imshow(disparity, cmap='gray', vmin=0, vmax=num_disp_values-1)
plt.show()
