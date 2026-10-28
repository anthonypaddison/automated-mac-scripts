#include <assert.h>
#include <stdio.h>
#include "lid-state.h"

static unsigned int muteCalls;
static bool muteSucceeds = true;

static bool recordMute(void)
{
    muteCalls++;
    return muteSucceeds;
}

int main(void)
{
    int previousState = -1;

    assert(handleLidState(&previousState, false, recordMute));
    assert(muteCalls == 0);
    assert(handleLidState(&previousState, true, recordMute));
    assert(muteCalls == 1);
    assert(handleLidState(&previousState, true, recordMute));
    assert(muteCalls == 1);
    assert(handleLidState(&previousState, false, recordMute));
    assert(muteCalls == 1); /* Opening the lid must never change the sound. */
    assert(handleLidState(&previousState, true, recordMute));
    assert(muteCalls == 2);

    previousState = -1;
    assert(handleLidState(&previousState, true, recordMute));
    assert(muteCalls == 3);

    previousState = 0;
    muteSucceeds = false;
    assert(!handleLidState(&previousState, true, recordMute));
    assert(previousState == 0); /* A failed mute must remain eligible to retry. */
    muteSucceeds = true;
    assert(handleLidState(&previousState, true, recordMute));
    assert(muteCalls == 5);

    puts("Passed: mute on close, no change on open, duplicate events, closed startup, failure retry.");
    return 0;
}
