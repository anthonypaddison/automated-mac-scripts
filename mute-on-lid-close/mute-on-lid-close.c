#include <CoreAudio/CoreAudio.h>
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <IOKit/IOMessage.h>
#include <IOKit/pwr_mgt/IOPM.h>
#include <IOKit/pwr_mgt/IOPMLib.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "lid-state.h"

static io_service_t rootDomain;
static io_connect_t powerConnection;
static int previousState = -1;

static void logEvent(const char *message)
{
    char timestamp[32];
    time_t now = time(NULL);
    struct tm local;
    localtime_r(&now, &local);
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", &local);
    fprintf(stderr, "%s %s\n", timestamp, message);
    fflush(stderr);
}

static int readLidState(void)
{
    CFTypeRef value = IORegistryEntryCreateCFProperty(
        rootDomain, CFSTR("AppleClamshellState"), kCFAllocatorDefault, 0);
    if (value == NULL) {
        return -1;
    }
    int state = -1;
    if (CFGetTypeID(value) == CFBooleanGetTypeID()) {
        state = CFBooleanGetValue((CFBooleanRef)value) ? 1 : 0;
    }
    CFRelease(value);
    return state;
}

static AudioDeviceID defaultOutput(void)
{
    AudioDeviceID device = kAudioObjectUnknown;
    UInt32 size = sizeof(device);
    AudioObjectPropertyAddress address = {
        kAudioHardwarePropertyDefaultOutputDevice,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain
    };
    OSStatus result = AudioObjectGetPropertyData(
        kAudioObjectSystemObject, &address, 0, NULL, &size, &device);
    return result == noErr ? device : kAudioObjectUnknown;
}

static const AudioObjectPropertyAddress muteAddress = {
    kAudioDevicePropertyMute,
    kAudioObjectPropertyScopeOutput,
    kAudioObjectPropertyElementMain
};

static bool muteDefaultOutput(void)
{
    AudioDeviceID device = defaultOutput();
    Boolean settable = false;
    OSStatus result = AudioObjectIsPropertySettable(device, &muteAddress, &settable);
    if (device == kAudioObjectUnknown || result != noErr || !settable) {
        logEvent("ERROR: current sound output does not support system mute.");
        return false;
    }
    UInt32 muted = 1;
    result = AudioObjectSetPropertyData(device, &muteAddress, 0, NULL, sizeof(muted), &muted);
    if (result != noErr) {
        fprintf(stderr, "ERROR: setting output mute failed (%d).\n", (int)result);
        return false;
    }
    logEvent("Lid closed: output muted.");
    return true;
}

static bool observeLid(bool closed)
{
    int oldState = previousState;
    bool success = handleLidState(&previousState, closed, muteDefaultOutput);
    if (!closed && oldState == 1) {
        logEvent("Lid opened: volume left unchanged.");
    }
    return success;
}

static void lidNotification(void *context, io_service_t service, natural_t type, void *argument)
{
    (void)context;
    (void)service;
    if (type == kIOPMMessageClamshellStateChange) {
        bool closed = ((uintptr_t)argument & kClamshellStateBit) != 0;
        if (!observeLid(closed)) {
            exit(EXIT_FAILURE);
        }
    }
}

/* The sleep callback acknowledges sleep only after the lid check and mute finish. */
static void powerNotification(void *context, io_service_t service, natural_t type, void *argument)
{
    (void)context;
    (void)service;
    if (type == kIOMessageCanSystemSleep) {
        IOAllowPowerChange(powerConnection, (intptr_t)argument);
    } else if (type == kIOMessageSystemWillSleep) {
        int state = readLidState();
        bool success = state != 1 || observeLid(true);
        IOAllowPowerChange(powerConnection, (intptr_t)argument);
        if (!success) {
            exit(EXIT_FAILURE);
        }
    } else if (type == kIOMessageSystemHasPoweredOn) {
        int state = readLidState();
        if (state >= 0 && !observeLid(state == 1)) {
            exit(EXIT_FAILURE);
        }
    }
}

int main(int argc, char **argv)
{
    if (argc > 2 || (argc == 2 && strcmp(argv[1], "--status") != 0)) {
        fprintf(stderr, "Usage: %s [--status]\n", argv[0]);
        return EXIT_FAILURE;
    }
    rootDomain = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOPMrootDomain"));
    if (!rootDomain || readLidState() < 0) {
        logEvent("ERROR: cannot read the MacBook lid state.");
        return EXIT_FAILURE;
    }
    if (argc == 2) {
        AudioDeviceID device = defaultOutput();
        UInt32 muted = 0;
        UInt32 size = sizeof(muted);
        Boolean settable = false;
        OSStatus result = AudioObjectGetPropertyData(device, &muteAddress, 0, NULL, &size, &muted);
        AudioObjectIsPropertySettable(device, &muteAddress, &settable);
        printf("Lid: %s; output mute: %s; system mute supported: %s\n",
            readLidState() ? "closed" : "open",
            result == noErr ? (muted ? "on" : "off") : "unavailable",
            settable ? "yes" : "no");
        IOObjectRelease(rootDomain);
        return result == noErr && settable ? EXIT_SUCCESS : EXIT_FAILURE;
    }

    IONotificationPortRef lidPort = IONotificationPortCreate(kIOMainPortDefault);
    io_object_t lidNotifier = IO_OBJECT_NULL;
    if (lidPort == NULL || IOServiceAddInterestNotification(lidPort, rootDomain,
            kIOGeneralInterest, lidNotification, NULL, &lidNotifier) != KERN_SUCCESS) {
        logEvent("ERROR: cannot subscribe to lid events.");
        return EXIT_FAILURE;
    }
    CFRunLoopAddSource(CFRunLoopGetCurrent(), IONotificationPortGetRunLoopSource(lidPort),
        kCFRunLoopDefaultMode);

    IONotificationPortRef powerPort = NULL;
    io_object_t powerNotifier = IO_OBJECT_NULL;
    powerConnection = IORegisterForSystemPower(NULL, &powerPort, powerNotification, &powerNotifier);
    if (powerConnection == IO_OBJECT_NULL || powerPort == NULL) {
        logEvent("ERROR: cannot subscribe to sleep events.");
        return EXIT_FAILURE;
    }
    CFRunLoopAddSource(CFRunLoopGetCurrent(), IONotificationPortGetRunLoopSource(powerPort),
        kCFRunLoopDefaultMode);
    int state = readLidState();
    if (state < 0 || !observeLid(state == 1)) {
        logEvent("ERROR: initial lid check failed.");
        return EXIT_FAILURE;
    }
    logEvent("Ready: watching lid events; opening the lid never restores sound.");
    CFRunLoopRun();
    return EXIT_SUCCESS;
}
