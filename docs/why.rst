Why another testing tool?
===========================

I have used Jenkins before. I was maintaining one instance in one of my VPS
instance.  The amount of RAM required by Jenkins was too much for my small VM.
I can admit that I am not a great sys-admin anyway.

As part of my daily job, I have to test the latest cloud images we build under
Fedora project. While doing so, I figured out that most of it can be automated
if we have a system to create/maintain/terminate cloud instances. Of course I
do not want any actual cloud, it will be a different monster to maintain.

This is the point where I came up with Tunir. Tunir is a simple testing tool
that will help me run automated tests for the cloud images. I kept the system
generic enough to execute any kind of tests people want.

The configuration is very minimal with Tunir. There is also a golang verion
called `gotun <https://gotun.rtfd.io>`_ which has better option to run the tests
inside OpenStack or AWS.
